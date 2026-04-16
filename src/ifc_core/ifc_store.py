from pathlib import Path
from typing import Any

import ifcopenshell

from ifc_core.models.ids import SpecificationManifest
from ifc_core.services.writer import ManifestWriter, apply_manifest_to_element

from .ids_store import IdsStore
from .models.ifc import (
    BulkSpecificationManifest,
    ClassificationTree,
    ComplexQuery,
    CountedItem,
    LayeredMaterialsSummary,
    MappingState,
    MappingStatus,
    ModelMappingSummary,
    ModelMetadata,
    ModificationResult,
    PSetSummary,
    SelectionAnalysis,
    SpatialNode,
)
from .services.discovery import DiscoveryAggregator
from .services.groups.base import AbstractGroupRepository
from .services.inspector import analyze_guids
from .services.metadata import get_model_info
from .services.query import QueryEngine
from .services.validator import check_mapping_status as validate_mapping_status


class IfcStore:
    """Primary public endpoint for IFC read, query, analysis, and write workflows."""

    def __init__(self, path: Path | None = None, model: Any = None):
        """Initialize store from an IFC file path or an existing in-memory model.

        Args:
            path: Path to an existing .ifc file. Required if model is None.
            model: An optional existing ifcopenshell model instance.

        Raises:
            ValueError: If neither path nor model is provided.
            FileNotFoundError: If path is provided but does not exist.
        """
        if model is not None:
            self._model = model
            self.path = Path(path) if path else None
        elif path:
            self.path = Path(path)
            if not self.path.exists():
                raise FileNotFoundError(f"No IFC file at {path}")
            self._model = ifcopenshell.open(str(self.path))
        else:
            raise ValueError("Either 'path' or 'model' must be provided to IfcStore")
        self._mapping_cache: dict[str, MappingStatus] = {}
        self.groups: AbstractGroupRepository | None = None
        self._discovery = DiscoveryAggregator(self._model)

    def bind_groups(self, repo: AbstractGroupRepository):
        """Inject a grouping storage backend into the store."""
        self.groups = repo

    def _clear_cache(self):
        """Invalidates the lazy cache when the model is modified."""
        self._mapping_cache.clear()

    @property
    def info(self) -> ModelMetadata:
        """Return structured file metadata.

        Returns:
            Model metadata with schema version, author, and timestamp.
        """
        return get_model_info(self._model, filename=self.path.name if self.path else None)

    def save(self, target_path: Path | None = None):
        """Persist model changes and clear mapping caches.

        Args:
            target_path: Optional save path. If omitted, overwrites original file.

        Returns:
            None.

        Raises:
            ValueError: If neither target_path nor self.path is available.
        """
        save_to = target_path or self.path
        if save_to is None:
            raise ValueError("No path available to save the IFC model.")
        self._model.write(str(save_to))
        self._clear_cache()

    # -------------------------------------------------------------------------
    # DISCOVERY API (Delegated to DiscoveryAggregator)
    # -------------------------------------------------------------------------

    def get_spatial_tree(self, parent_guid: str | None = None) -> list[SpatialNode]:
        """Return spatial hierarchy nodes for UI tree views."""
        return self._discovery.get_spatial_tree(parent_guid)

    def get_psets(self) -> list[PSetSummary]:
        """List unique property sets with occurrence counts and parameter names."""
        return self._discovery.get_psets()

    def get_materials(self) -> list[CountedItem]:
        """List known materials with usage counts across elements."""
        return self._discovery.get_materials()

    def get_entity_counts(self) -> list[CountedItem]:
        """List IfcProduct entity types with occurrence counts."""
        return self._discovery.get_entity_counts()

    def get_classification_tree(self) -> ClassificationTree:
        """Return full model classification tree including unclassified bucket."""
        return self._discovery.get_classification_tree()

    def get_layered_materials(self) -> LayeredMaterialsSummary:
        """Return layered material aggregates."""
        return self._discovery.get_layered_materials()

    # -------------------------------------------------------------------------
    # QUERY & INSPECTION ENGINE
    # -------------------------------------------------------------------------

    def analyze_guids(self, guids: list[str]) -> SelectionAnalysis:
        """Compute shared attributes and PSets for the given element GUIDs.

        Mixed values are represented through SharedValue.is_mixed.

        Args:
            guids: Element GUIDs to compare.

        Returns:
            Common attribute and property-set values across the selection.
        """
        return analyze_guids(self._model, guids)

    def execute_query(
        self, query: ComplexQuery, ids_store: IdsStore | None = None
    ) -> list[str]:
        """
        Execute a recursive query tree and return matching element GUIDs.

        Args:
            query: Root query expression using logical operators and criteria.
            ids_store: Optional IDS context, required for MappingStatus filters.

        Returns:
            Matching element GUIDs.
        """
        engine = QueryEngine(self._model)
        if ids_store:
            engine.inject_context(self, ids_store)
        return engine.execute(query)

    # -------------------------------------------------------------------------
    # MODIFICATION & MAPPING ENGINE
    # -------------------------------------------------------------------------

    def apply_specification(
        self, manifest: SpecificationManifest
    ) -> list[ModificationResult]:
        """
        Apply one resolved specification manifest to one IFC element.

        Args:
            manifest: App-resolved contract with final values.

        Returns:
            List of write operation results.
        """
        self._clear_cache()
        return apply_manifest_to_element(self._model, manifest)

    def apply_bulk_manifest(
        self, manifest: BulkSpecificationManifest
    ) -> list[ModificationResult]:
        """
        Apply one resolved requirement set to many elements.

        Args:
            manifest: Bulk write contract with GUID list and requirements.

        Returns:
            List of write operation results.
        """
        self._clear_cache()
        writer = ManifestWriter(self._model)
        return writer.apply_bulk_manifest(manifest)

    def check_mapping_status(self, ids_store: IdsStore) -> list[MappingStatus]:
        """
        Evaluate mapping status for all IfcProduct/specification combinations.

        Args:
            ids_store: IDS definitions used to validate the IFC model.

        Cache behavior:
            Uses store-local lazy caching keyed by element GUID and spec name.

        Returns:
            One MappingStatus per element/specification pair.
        """
        states = []
        for spec in ids_store.specifications:
            # Narrow search scope to the specific entity type if defined in IDS
            entity_type = "IfcProduct"
            for req in spec.applicability:
                if req.type.lower() in ("entity", "ifcentity", "class"):
                    entity_type = req.value or req.name or "IfcProduct"
                    break

            for element in self._model.by_type(entity_type):
                guid = getattr(element, "GlobalId", None)
                if not guid:
                    continue

                cache_key = f"{guid}_{spec.name}"
                if cache_key in self._mapping_cache:
                    status = self._mapping_cache[cache_key]
                else:
                    status = validate_mapping_status(element, spec)
                    self._mapping_cache[cache_key] = status

                states.append(status)
        return states

    def get_mapping_summary(self, ids_store: IdsStore) -> list[ModelMappingSummary]:
        """
        Aggregate mapping-state counters per specification.

        Args:
            ids_store: IDS definitions used to validate the IFC model.

        Returns:
            Dashboard-friendly summary DTOs.
        """
        status_list = self.check_mapping_status(ids_store)

        summaries_dict = {}
        for spec in ids_store.specifications:
            summaries_dict[spec.name] = {
                "total": 0,
                "compliant": 0,
                "invalid": 0,
                "incomplete": 0,
                "unmapped": 0,
            }

        for st in status_list:
            if st.spec_name not in summaries_dict:
                continue

            sd = summaries_dict[st.spec_name]
            sd["total"] += 1
            if st.state == MappingState.COMPLIANT:
                sd["compliant"] += 1
            elif st.state == MappingState.INVALID:
                sd["invalid"] += 1
            elif st.state == MappingState.INCOMPLETE:
                sd["incomplete"] += 1
            elif st.state == MappingState.UNMAPPED:
                sd["unmapped"] += 1

        return [
            ModelMappingSummary(
                spec_name=name,
                total_applicable=data["total"],
                compliant_count=data["compliant"],
                invalid_count=data["invalid"],
                incomplete_count=data["incomplete"],
                unmapped_count=data["unmapped"],
            )
            for name, data in summaries_dict.items()
        ]

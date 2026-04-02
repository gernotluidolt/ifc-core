from pathlib import Path
from typing import Any, Dict, List, Optional
import ifcopenshell

from ifc_core.models.ids import SpecificationManifest
from ifc_core.services.writer import (
    apply_manifest_to_element,
    ManifestWriter
)
from .models.ifc import (
    ModelMetadata, ModificationResult, MappingStatus, ModelMappingSummary, 
    BulkSpecificationManifest, MappingState, SpatialNode, CountedItem, 
    PSetSummary, SelectionAnalysis, ComplexQuery
)
from .services.metadata import get_model_info
from .services.validator import check_mapping_status as validate_mapping_status
from .services.discovery import get_spatial_tree, get_psets, get_materials
from .services.inspector import analyze_guids
from .services.query import QueryEngine
from .ids_store import IdsStore


class IfcStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        if not self.path.exists():
            raise FileNotFoundError(f"No IFC file at {path}")
        self._model = ifcopenshell.open(str(self.path))
        self._mapping_cache: Dict[str, MappingStatus] = {}

    def _clear_cache(self):
        """Invalidates the lazy cache when the model is modified."""
        self._mapping_cache.clear()

    @property
    def info(self) -> ModelMetadata:
        """Returns structured metadata about the file."""
        return get_model_info(self._model)

    def save(self, target_path: Optional[Path] = None):
        """Saves changes back to disk and invalidates cache."""
        save_to = target_path or self.path
        self._model.write(str(save_to))
        self._clear_cache()

    # -------------------------------------------------------------------------
    # DISCOVERY API
    # -------------------------------------------------------------------------

    def get_spatial_tree(self, parent_guid: Optional[str] = None) -> List[SpatialNode]:
        """Creates the visual topology mapping Sites -> Buildings -> Storey -> Entities"""
        return get_spatial_tree(self._model, parent_guid)

    def get_psets(self) -> List[PSetSummary]:
        """Provides a map of all PSets assigned within the document and their parameters."""
        return get_psets(self._model)

    def get_materials(self) -> List[CountedItem]:
        """Lists all established materials and the number of elements using them."""
        return get_materials(self._model)

    # -------------------------------------------------------------------------
    # QUERY & INSPECTION ENGINE
    # -------------------------------------------------------------------------

    def analyze_guids(self, guids: List[str]) -> SelectionAnalysis:
        """Performs data intersection across multiple geometry elements checking commonalities."""
        return analyze_guids(self._model, guids)

    def execute_query(self, query: ComplexQuery, ids_store: Optional[IdsStore] = None) -> List[str]:
        """
        Recursive GUID filter functionality. 
        Supports MappingStatus filtering recursively across nested conditions.
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
    ) -> List[ModificationResult]:
        """
        Takes a resolved manifest from the App and commits it to the IFC model.
        """
        self._clear_cache()
        return apply_manifest_to_element(self._model, manifest)

    def apply_bulk_manifest(
        self, manifest: BulkSpecificationManifest
    ) -> List[ModificationResult]:
        """
        Efficiently writes the same data to multiple Express IDs natively.
        """
        self._clear_cache()
        writer = ManifestWriter(self._model)
        return writer.apply_bulk_manifest(manifest)

    def check_mapping_status(self, ids_store: IdsStore) -> List[MappingStatus]:
        """
        Compares every element against every applicable IDS Spec.
        Utilizes a request-scoped lazy cache to prevent redundant recalculations.
        """
        states = []
        for spec in ids_store.specifications:
            for element in self._model.by_type("IfcProduct"):
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

    def get_mapping_summary(self, ids_store: IdsStore) -> List[ModelMappingSummary]:
        """
        Aggregates data for the high-level project overview.
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
                unmapped_count=data["unmapped"]
            )
            for name, data in summaries_dict.items()
        ]

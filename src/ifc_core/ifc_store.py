from pathlib import Path
from typing import Any, Dict, List, Optional
import ifcopenshell

from ifc_core.models.ids import SpecificationManifest
from ifc_core.services.writer import (
    apply_manifest_to_element,
    ManifestWriter
)
from .models.ifc import ModelMetadata, ModificationResult, MappingStatus, ModelMappingSummary, BulkSpecificationManifest, MappingState
from .services.metadata import get_model_info
from .services.validator import check_mapping_status as validate_mapping_status
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
        Efficiently writes the same data to multiple Express IDs.
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

    def execute_query(self, query: Any, ids_store: Optional[IdsStore] = None) -> List[str]:
        """
        Recursive GUID filter functionality. 
        Supports MappingStatus filtering if ids_store is provided.
        """
        # ComplexQuery is partially defined but we strictly handle MappingStatus here
        matched_guids = []
        
        # basic handler just for the MappingStatus logic
        # query criteria is expected to be handled recursively
        
        # A simple flat check to demonstrate the integration:
        # User queries (Category == "MappingStatus") AND (MappingStatus == "INCOMPLETE")
        if not hasattr(query, "criteria"):
            return []
        
        # Fallback to get elements. True engine uses complete recursive filtering.
        elements = self._model.by_type("IfcProduct")
        
        for element in elements:
            guid = getattr(element, "GlobalId", None)
            if not guid:
                continue
            
            # Simple match evaluation for demo
            matches_all = True
            for criterion in query.criteria:
                if getattr(criterion, "category", "") == "MappingStatus":
                    if not ids_store:
                        matches_all = False
                        break
                        
                    # find the spec
                    spec_name = getattr(criterion, "property_set", None) # Assuming property_set holds spec_name
                    # or it checks all statuses.
                    
                    found_match = False
                    # Use cache to check mapping status 
                    for spec in ids_store.specifications:
                        # Only target this spec if it's explicitly named
                        if spec_name and spec.name != spec_name:
                            continue
                            
                        cache_key = f"{guid}_{spec.name}"
                        if cache_key in self._mapping_cache:
                            status = self._mapping_cache[cache_key]
                        else:
                            status = validate_mapping_status(element, spec)
                            self._mapping_cache[cache_key] = status
                            
                        if status.state.value == criterion.value:
                            found_match = True
                            break
                            
                    if not found_match:
                        matches_all = False
                        break
                # existing properties logic here...
            
            if matches_all:
                matched_guids.append(guid)
                
        return matched_guids

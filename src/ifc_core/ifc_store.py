from pathlib import Path
from typing import Any, Dict, List, Optional
import ifcopenshell

from ifc_core.models.ids import SpecificationManifest
from ifc_core.services.writer import (
    add_pset_to_element,
    apply_manifest_to_element,
    apply_manifest_to_element,
)
from .models.ifc import ModelMetadata, ModificationResult
from .services.metadata import get_model_info


class IfcStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        if not self.path.exists():
            raise FileNotFoundError(f"No IFC file at {path}")
        self._model = ifcopenshell.open(str(self.path))

    @property
    def info(self) -> ModelMetadata:
        """Returns structured metadata about the file."""
        return get_model_info(self._model)

    def save(self, target_path: Optional[Path] = None):
        """Saves changes back to disk."""
        save_to = target_path or self.path
        self._model.write(str(save_to))

    def add_custom_data(
        self, guid: str, pset_name: str, data: Dict[str, Any]
    ) -> ModificationResult:
        """
        Adds a Property Set to a specific element by its GlobalID.
        Example: store.add_custom_data("123...", "MyPset", {"Status": "Checked"})
        """
        return add_pset_to_element(self._model, guid, pset_name, data)

    def apply_specification(
        self, manifest: SpecificationManifest
    ) -> List[ModificationResult]:
        """
        Takes a resolved manifest from the App and commits it to the IFC model.
        """
        return apply_manifest_to_element(self._model, manifest)

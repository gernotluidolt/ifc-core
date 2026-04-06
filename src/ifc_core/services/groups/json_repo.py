import json
from pathlib import Path

from ifc_core.models.groups import BimGroup, BimGroupSummary

from .base import AbstractGroupRepository


class JsonFileGroupRepository(AbstractGroupRepository):
    """BIM Group storage using a sidecar JSON file.

    By default, it looks for {ifc_filename}_groups.json.
    """

    def __init__(self, ifc_path: Path):
        """Initialize the repository tied to an IFC document path.

        Args:
            ifc_path: Path to the .ifc file used as a reference.
        """
        self.ifc_path = Path(ifc_path)
        self.sidecar_path = self.ifc_path.parent / f"{self.ifc_path.stem}_groups.json"

    def _load(self) -> dict[str, list[str]]:
        """Read the group manifest from disk."""
        if not self.sidecar_path.exists():
            return {}
        try:
            with open(self.sidecar_path, encoding="utf-8") as fh:
                data = json.load(fh)
                return {str(k): list(v or []) for k, v in data.items()}
        except Exception:
            return {}

    def _save(self, data: dict[str, list[str]]) -> bool:
        """Write the group manifest to disk."""
        try:
            with open(self.sidecar_path, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2)
            return True
        except Exception:
            return False

    def get_all(self) -> list[BimGroupSummary]:
        """Return a list of all groups and their element counts."""
        data = self._load()
        return [BimGroupSummary(name=k, count=len(v)) for k, v in data.items()]

    def get_group(self, name: str) -> BimGroup | None:
        """Return a specific group by name."""
        data = self._load()
        if name not in data:
            return None
        return BimGroup(name=name, element_guids=data[name])

    def save_group(self, group: BimGroup) -> bool:
        """Update or create a group's metadata."""
        data = self._load()
        data[group.name] = group.element_guids
        return self._save(data)

    def delete_group(self, name: str) -> bool:
        """Permanently delete a group."""
        data = self._load()
        if name in data:
            del data[name]
            return self._save(data)
        return False

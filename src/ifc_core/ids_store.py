from pathlib import Path
from typing import List, Optional
from .models.ids import IdsSpecification
from .services.ids_reader import parse_ids_file


class IdsStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        if not self.path.exists():
            raise FileNotFoundError(f"IDS file not found at {path}")

        # Parse the specifications immediately on load
        self._specs: List[IdsSpecification] = parse_ids_file(self.path)

    @property
    def specifications(self) -> List[IdsSpecification]:
        """Provides easy access to all specifications found in the IDS."""
        return self._specs

    def get_spec_by_name(self, name: str) -> Optional[IdsSpecification]:
        return next((s for s in self._specs if s.name == name), None)

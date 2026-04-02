from pathlib import Path
from typing import List, Optional
from .models.ids import IdsSpecification
from .services.ids_reader import parse_ids_file


class IdsStore:
    """Primary public endpoint for loading and querying IDS specifications."""

    def __init__(self, path: Path):
        """Load and parse an IDS file into strongly typed specification DTOs.

        Args:
            path: Path to an existing .ids file.

        Raises:
            FileNotFoundError: If the IDS file does not exist.
        """
        self.path = Path(path)
        if not self.path.exists():
            raise FileNotFoundError(f"IDS file not found at {path}")

        # Parse the specifications immediately on load
        self._specs: List[IdsSpecification] = parse_ids_file(self.path)

    @property
    def specifications(self) -> List[IdsSpecification]:
        """Return all parsed IDS specifications from the loaded file.

        Returns:
            Parsed IDS specifications in file order.
        """
        return self._specs

    def get_spec_by_name(self, name: str) -> Optional[IdsSpecification]:
        """Return the first specification matching name, or None if absent.

        Args:
            name: Specification name to look up.

        Returns:
            The matching specification, or None when not found.
        """
        return next((s for s in self._specs if s.name == name), None)

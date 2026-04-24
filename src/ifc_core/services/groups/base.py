from abc import ABC, abstractmethod

from ifc_core.models.groups import BimGroup, BimGroupSummary


class AbstractGroupRepository(ABC):
    """Pythonic interface for element group persistence.

    This ABC allows ifc-core to operate on grouping-metadata without
    knowing the underlying storage backend (JSON, SQLite, etc.).
    """

    @abstractmethod
    def get_all(self) -> list[BimGroupSummary]:
        """Return a summary list of all existing groups."""
        pass

    @abstractmethod
    def get_group(self, name: str) -> BimGroup | None:
        """Fetch a full group by name with its corresponding GUIDs."""
        pass

    @abstractmethod
    def save_group(self, group: BimGroup) -> bool:
        """Persist or update a group's metadata."""
        pass

    @abstractmethod
    def delete_group(self, name: str) -> bool:
        """Permanently remove a group from the storage."""
        pass

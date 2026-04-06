
from pydantic import BaseModel


class BimGroup(BaseModel):
    """A logical collection of element GUIDs used for organization and filtering."""

    name: str
    element_guids: list[str]


class BimGroupSummary(BaseModel):
    """Metadata summary of a BIM Group for list-views (name and item count)."""

    name: str
    count: int

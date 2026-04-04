from pydantic import BaseModel
from typing import List


class BimGroup(BaseModel):
    """A logical collection of element GUIDs used for organization and filtering."""

    name: str
    element_guids: List[str]


class BimGroupSummary(BaseModel):
    """Metadata summary of a BIM Group for list-views (name and item count)."""

    name: str
    count: int

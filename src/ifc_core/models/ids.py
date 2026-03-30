from pydantic import BaseModel, Field
from typing import List, Optional, Union


class IdsRequirement(BaseModel):
    type: str = Field(
        ..., description="Property, Attribute, Material, or Classification"
    )
    name: Optional[str] = None
    value: Optional[str] = None
    property_set: Optional[str] = None
    instructions: Optional[str] = None


class IdsSpecification(BaseModel):
    name: str
    identifier: Optional[str] = None
    description: Optional[str] = None
    instructions: Optional[str] = None
    min_occurs: int = 0
    max_occurs: Optional[Union[int, str]] = "unbounded"

    # Applicability: The "Filter" (e.g., IfcWall)
    applicability: List[IdsRequirement]

    # Requirements: The "Rules" (e.g., Must have Pset_WallCommon.LoadBearing)
    requirements: List[IdsRequirement]

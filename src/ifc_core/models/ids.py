from pydantic import BaseModel, Field
from typing import List, Optional, Any


class IdsRequirement(BaseModel):
    type: str  # Property, Attribute, Material, etc.
    name: Optional[str] = None
    value: Optional[str] = None
    property_set: Optional[str] = None
    instructions: Optional[str] = None

    # NEW: Logic for Ambiguity/Restrictions
    options: List[str] = Field(default_factory=list)  # ["Internal", "External"]
    min_inclusive: Optional[float] = None
    max_inclusive: Optional[float] = None


class IdsSpecification(BaseModel):
    name: str
    identifier: Optional[str] = None
    applicability: List[IdsRequirement]
    requirements: List[IdsRequirement]


class ConcreteRequirement(BaseModel):
    """The App's resolved choice."""

    type: str
    name: str
    value: Any
    property_set: Optional[str] = None


class SpecificationManifest(BaseModel):
    """The final contract handed back to the package."""

    element_guid: str
    specification_name: str
    requirements: List[ConcreteRequirement]

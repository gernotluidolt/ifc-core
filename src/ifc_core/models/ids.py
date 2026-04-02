from pydantic import BaseModel, Field
from typing import List, Optional, Any


class IdsRequirement(BaseModel):
    """A single IDS facet describing applicability or required data.

    The same shape is used for both:
    - specification applicability (which elements are in scope), and
    - specification requirements (which values must be present).
    """

    type: str  # Property, Attribute, Material, etc.
    name: Optional[str] = None
    value: Optional[str] = None
    property_set: Optional[str] = None
    instructions: Optional[str] = None
    options: List[str] = Field(default_factory=list)  # ["Internal", "External"]
    min_inclusive: Optional[float] = None
    max_inclusive: Optional[float] = None


class IdsSpecification(BaseModel):
    """Parsed representation of one IDS specification block."""

    name: str
    identifier: Optional[str] = None
    applicability: List[IdsRequirement]
    requirements: List[IdsRequirement]


class ConcreteRequirement(BaseModel):
    """A requirement resolved by the application and ready to be written.

    This DTO is intentionally ambiguity-free. Any user-facing choice
    (such as selecting one option from IDS enumerations) must already
    be resolved before creating this object.
    """

    type: str
    name: str
    value: Any
    property_set: Optional[str] = None


class SpecificationManifest(BaseModel):
    """Write contract for applying one IDS specification to one element.

    Endpoint:
        Used by IfcStore.apply_specification(...).
    """

    element_guid: str
    specification_name: str
    requirements: List[ConcreteRequirement]

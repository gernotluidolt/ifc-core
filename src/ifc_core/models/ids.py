from typing import Any

from pydantic import BaseModel, Field


class IdsRequirement(BaseModel):
    """A single IDS facet describing applicability or required data.

    The same shape is used for both:
    - specification applicability (which elements are in scope), and
    - specification requirements (which values must be present).
    """

    type: str  # Property, Attribute, Material, etc.
    name: str | None = None
    value: str | None = None
    property_set: str | None = None
    instructions: str | None = None
    options: list[str] = Field(default_factory=list)  # ["Internal", "External"]
    data_type: str | None = None  # e.g., "decimal", "integer", "boolean", "string"
    min_inclusive: float | None = None
    max_inclusive: float | None = None
    cardinality: str | None = None
    relation: str | None = None


class IdsSpecification(BaseModel):
    """Parsed representation of one IDS specification block."""

    name: str
    identifier: str | None = None
    applicability: list[IdsRequirement]
    requirements: list[IdsRequirement]


class ConcreteRequirement(BaseModel):
    """A requirement resolved by the application and ready to be written.

    This DTO is intentionally ambiguity-free. Any user-facing choice
    (such as selecting one option from IDS enumerations) must already
    be resolved before creating this object.
    """

    type: str
    name: str
    value: Any
    property_set: str | None = None
    data_type: str | None = None
    relation: str | None = None


class SpecificationManifest(BaseModel):
    """Write contract for applying one IDS specification to one element.

    Endpoint:
        Used by IfcStore.apply_specification(...).
    """

    element_guid: str
    specification_name: str
    requirements: list[ConcreteRequirement]

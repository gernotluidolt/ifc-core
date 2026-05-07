from enum import Enum
from typing import Any, Union

from pydantic import BaseModel

from .ids import ConcreteRequirement, IdsRequirement


class ModelMetadata(BaseModel):
    """Metadata extracted from the IFC file header and project context."""

    schema_version: str
    author: str
    timestamp: str
    file_name: str | None = None
    has_multilayered_elements: bool = False


class ModificationResult(BaseModel):
    """Result of applying a write operation to one IFC element."""

    success: bool
    msg: str
    express_id: int | None = None


class MappingState(str, Enum):
    """Mapping states returned by IDS validation endpoints."""

    UNMAPPED = "UNMAPPED"  # Element fails applicability or lacks properties
    INCOMPLETE = "INCOMPLETE"  # Required parameters exist, but missing values
    INVALID = "INVALID"  # Required parameters exist, but violate constraints
    COMPLIANT = "COMPLIANT"  # All IDS requirements met


class MappingStatus(BaseModel):
    """Validation outcome for one element against one specification."""

    element_guid: str
    spec_name: str
    state: MappingState
    missing_requirements: list[IdsRequirement] = []
    invalid_requirements: list[IdsRequirement] = []


class ModelMappingSummary(BaseModel):
    """Aggregate mapping counts for one specification."""

    spec_name: str
    total_applicable: int
    compliant_count: int
    invalid_count: int
    incomplete_count: int
    unmapped_count: int


class BulkSpecificationManifest(BaseModel):
    """Resolved write contract for applying one requirement set to many elements."""

    element_guids: list[str]
    specification_name: str
    requirements: list[ConcreteRequirement]


class SpatialNode(BaseModel):
    """Recursive spatial tree node used by discovery endpoints."""

    guid: str
    name: str
    type: str  # IfcSite, IfcBuilding, IfcBuildingStorey
    element_count: int
    has_children: bool
    children: list["SpatialNode"] | None = None


class CountedItem(BaseModel):
    """Name/count pair used by discovery endpoints."""

    name: str
    element_count: int


class PSetSummary(CountedItem):
    """Property set summary including the parameter names it exposes and their values."""

    parameters: list[str] = []
    children: list["PSetSummary"] = []


class ClassificationNode(BaseModel):
    """Tree node used for classification discovery responses."""

    id: str
    type: str  # system, reference, element
    name: str
    count: int | None = None
    children: list["ClassificationNode"] = []


class ClassificationTree(BaseModel):
    """Classification discovery response payload."""

    tree: list[ClassificationNode]
    total_elements: int


class LayeredMaterialItem(CountedItem):
    """Layered material summary with layer count metadata."""

    layer_count: int


class LayeredMaterialsSummary(BaseModel):
    """Layered material discovery response payload."""

    materials: list[LayeredMaterialItem]
    total_elements: int


class ComparisonOperator(str, Enum):
    """Comparison operators supported by query filters."""

    EQUALS = "=="
    NOT_EQUALS = "!="
    GREATER_THAN = ">"
    LESS_THAN = "<"
    CONTAINS = "contains"


class FilterCriterion(BaseModel):
    """Atomic predicate used in a ComplexQuery expression tree."""

    category: str  # "Attribute", "PSet", "Material", "Story", "MappingStatus"
    name: str | None = (
        None  # e.g., "LoadBearing". None if checking just Pset/Material existence
    )
    operator: ComparisonOperator
    value: Any
    property_set: str | None = None  # Required if category == "PSet"


class ComplexQuery(BaseModel):
    """Recursive boolean query contract supporting AND, OR, and NOT."""

    logical_op: str = "AND"  # "AND", "OR", "NOT"
    criteria: list[Union[FilterCriterion, "ComplexQuery"]]


class SharedValue(BaseModel):
    """Value container that marks whether an inspected field is mixed."""

    value: Any
    is_mixed: bool = (
        False  # True if the selected GUIDs have different values for this key
    )
    other_values: list[Any] = []  # If mixed, contains the unique set of values present


class SelectionAnalysis(BaseModel):
    """Shared values returned when inspecting multiple element GUIDs."""

    common_attributes: dict[str, SharedValue]
    common_psets: dict[str, dict[str, SharedValue]]
    common_classifications: dict[str, SharedValue] = {}
    common_materials: dict[str, SharedValue] = {}

class AnchorGroup(BaseModel):
    """A cluster of elements sharing a common anchor value."""

    value: str
    count: int


class AnchorGroupsResponse(BaseModel):
    """Response payload for anchor-based discovery."""

    ok: bool
    anchor_name: str
    pivot_mode: str
    groups: list[AnchorGroup]
    unanchored_count: int
    total_count: int
    storey_guid: str | None = None
    error: str | None = None


class AnchorSelectResponse(BaseModel):
    """Response payload for anchor selection actions."""

    ok: bool
    selected_count: int
    candidate_count: int
    error: str | None = None

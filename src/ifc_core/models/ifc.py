from pydantic import BaseModel
from typing import Optional, List, Dict, Union, Any
from enum import Enum
from .ids import IdsRequirement, ConcreteRequirement


class ModelMetadata(BaseModel):
    schema_version: str
    author: str
    timestamp: str


class ModificationResult(BaseModel):
    success: bool
    msg: str
    express_id: Optional[int] = None


class MappingState(str, Enum):
    UNMAPPED = "UNMAPPED"         # Element fails applicability or lacks properties
    INCOMPLETE = "INCOMPLETE"     # Required parameters exist, but missing values
    INVALID = "INVALID"           # Required parameters exist, but violate constraints
    COMPLIANT = "COMPLIANT"       # All IDS requirements met


class MappingStatus(BaseModel):
    element_guid: str
    spec_name: str
    state: MappingState
    missing_requirements: List[IdsRequirement] = []
    invalid_requirements: List[IdsRequirement] = []


class ModelMappingSummary(BaseModel):
    spec_name: str
    total_applicable: int
    compliant_count: int
    invalid_count: int
    incomplete_count: int
    unmapped_count: int


class BulkSpecificationManifest(BaseModel):
    element_guids: List[str]
    specification_name: str
    requirements: List[ConcreteRequirement]


class SpatialNode(BaseModel):
    """Recursive node for spatial hierarchy. children=None indicates lazy-loading required."""
    guid: str
    name: str
    type: str  # IfcSite, IfcBuilding, IfcBuildingStorey
    element_count: int
    has_children: bool
    children: Optional[List["SpatialNode"]] = None


class CountedItem(BaseModel):
    name: str
    element_count: int


class PSetSummary(CountedItem):
    """A map of what PSets exist and which parameters they contain."""
    parameters: List[str]


class ComparisonOperator(str, Enum):
    EQUALS = "=="
    NOT_EQUALS = "!="
    GREATER_THAN = ">"
    LESS_THAN = "<"
    CONTAINS = "contains"


class FilterCriterion(BaseModel):
    category: str # "Attribute", "PSet", "Material", "Story", "MappingStatus"
    name: Optional[str] = None # e.g., "LoadBearing". None if checking just Pset/Material existence
    operator: ComparisonOperator
    value: Any
    property_set: Optional[str] = None # Required if category == "PSet"


class ComplexQuery(BaseModel):
    """The recursive contract for cascading AND/OR/NOT logic."""
    logical_op: str = "AND" # "AND", "OR", "NOT"
    criteria: List[Union[FilterCriterion, "ComplexQuery"]]


class SharedValue(BaseModel):
    value: Any
    is_mixed: bool = False # True if the selected GUIDs have different values for this key


class SelectionAnalysis(BaseModel):
    """
    Requirements for Implementation:
    1. Only return Psets/Attributes present in EVERY provided GUID.
    2. If values differ across GUIDs, mark is_mixed=True.
    """
    common_attributes: Dict[str, SharedValue]
    common_psets: Dict[str, Dict[str, SharedValue]]

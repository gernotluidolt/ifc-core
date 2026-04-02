from pydantic import BaseModel
from typing import Optional, List
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

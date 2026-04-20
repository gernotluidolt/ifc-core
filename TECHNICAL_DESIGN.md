# Technical Design: ifc_core

The `ifc_core` package is a **Stateless Data Engine**. It provides high-performance methods to query, analyze, and modify IFC data based on external instructions (DTOs).

---

## 1. Discovery DTOs (Read-Only)
These models define how to describe the IFC file to the outside world.

```Python
from pydantic import BaseModel, Field
from typing import List, Optional, Any, Union, Dict

class ModelMetadata(BaseModel):
    filename: str
    ifc_version: str
    site_count: int
    story_count: int
    author: str

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
```

---

## 2. Group Management DTOs
Support for logical groupings of IFC elements stored in sidecar repositories.

```Python
class BimGroupSummary(BaseModel):
    name: str
    count: int

class BimGroup(BaseModel):
    name: str
    element_guids: List[str]
```

---

## 3. The Query Engine 
A recursive search algorithm that translates this DTO into `ifcopenshell` filtered collections.
```Python
class ComparisonOperator(str, Enum):
    EQUALS = "=="
    NOT_EQUALS = "!="
    GREATER_THAN = ">"
    LESS_THAN = "<"
    CONTAINS = "contains"

class FilterCriterion(BaseModel):
    category: str # "Attribute", "PSet", "Material", "Story", "Geometry", "MappingStatus"
    name: str     # e.g., "LoadBearing", "Height"
    operator: ComparisonOperator
    value: Any
    property_set: Optional[str] = None # Required if category == "PSet"

class ComplexQuery(BaseModel):
    """The recursive contract for cascading AND/OR/NOT logic."""
    logical_op: str = "AND" # "AND", "OR", "NOT"
    criteria: List[Union[FilterCriterion, "ComplexQuery"]]
```

---

## 4. Analysis DTOs (Multi-Element Inspection)
Provides the logic to "intersect" data across many elements to find commonalities and conflicts.
```Python
class SharedValue(BaseModel):
    value: Any
    is_mixed: bool = False # True if the selected GUIDs have different values for this key

class SelectionAnalysis(BaseModel):
    common_attributes: Dict[str, SharedValue]
    common_psets: Dict[str, Dict[str, SharedValue]]
    common_classifications: Dict[str, SharedValue]
```

---

## 5. Architectural Component: Services & Aggregators

The package has transitioned from a flat service structure to a granular, domain-specific organization under `src/ifc_core/services/`.

### The Discovery Stack (Read Optimization)
Discovery logic is split into specialized modules, all unified by the `DiscoveryAggregator`.

- **`services.discovery.spatial`**: Spatial hierarchy and decomposition.
- **`services.discovery.psets`**: Property set scanning and caching.
- **`services.discovery.classifications`**: Classification tree traversals.
- **`services.discovery.materials`**: Material association resolution.

```Python
class DiscoveryAggregator:
    """Unified entry point for read-only model discovery."""
    def __init__(self, model: ifcopenshell.file): ...
    def get_spatial_tree(self) -> List[SpatialNode]: ...
    def get_psets(self) -> List[PSetSummary]: ...
    def get_classification_tree(self) -> List[ClassificationNode]: ...
```

### The Groups Stack (Sidecar Persistence)
Uses an Abstract Base Class to decouple `ifc-core` from specific storage implementations.

- **`AbstractGroupRepository`**: Interface for CRUD on element groups.
- **`JsonFileGroupRepository`**: Current implementation using `{filename}_groups.json` sidecar files.

---

## 6. Mapping State & Progress DTOs

```Python
class MappingState(str, Enum):
    UNMAPPED = "UNMAPPED"
    INCOMPLETE = "INCOMPLETE"
    INVALID = "INVALID"
    COMPLIANT = "COMPLIANT"

class MappingStatus(BaseModel):
    element_guid: str
    spec_name: str
    state: MappingState
    missing_requirements: List[IdsRequirement] 
    invalid_requirements: List[IdsRequirement] 
```

---

## 7. Operational Core: `IfcStore`

The `IfcStore` remains the primary integration point, orchestrating services:

| **Method Category**    | **Implementation Strategy**                                                                 |
| ---------------------- | ------------------------------------------------------------------------------------------- |
| **Discovery**          | Delegates to `DiscoveryAggregator` for cached tree lookups.                                |
| **Querying**           | Uses `QueryEngine` to evaluate `ComplexQuery` trees against `ifcopenshell` selectors.      |
| **Analysis**           | Intersects common overlaps explicitly resolving edge `<Mixed>` property occurrences.       |
| **Groups**             | Injected with an `AbstractGroupRepository` to handle logical element sets.                  |
| **Enrichment/Writing** | Uses `ManifestWriter` to apply `SpecificationManifest` contracts with material pooling.     |

---

## 8. Architectural Guardrails

1. **Protocol-First**: All data changes must originate in `ifc_core.models`.
2. **Stateless Logic**: Services should not hold state beyond internal performance caches; they must operate on the passed `ifcopenshell.file`.
3. **Deterministic Mapping**: Mapping status must be calculated on-the-fly to ensure it always reflects the current model state.

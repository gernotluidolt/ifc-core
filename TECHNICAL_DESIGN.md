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
## 2. The Query Engine 
A recursive search algorithm that translates this DTO into `ifcopenshell` filtered collections.
```Python
class ComparisonOperator(str, Enum):
    EQUALS = "=="
    NOT_EQUALS = "!="
    GREATER_THAN = ">"
    LESS_THAN = "<"
    CONTAINS = "contains"

class FilterCriterion(BaseModel):
    category: str # "Attribute", "PSet", "Material", "Story", "Geometry"
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
## 3. Analysis DTOs (Multi-Element Inspection)
Provides the logic to "intersect" data across many elements to find commonalities and conflicts.
```Python
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
```

---

## 4. Core Package Requirements (Methods)
The `IfcStore` class must implement the following "Engine" methods:

| **Method**             | **Input**      | **Returns**         | **Implementation Detail**                         |
| ---------------------- | -------------- | ------------------- | ------------------------------------------------- |
| `get_model_metadata()` | -              | `ModelMetadata`     | Extract from Header and `IfcProject`.             |
| `get_spatial_tree()`   | `parent_guid`  | `List[SpatialNode]` | If `parent_guid` is None, return Sites.           |
| `get_psets()`          | -              | `List[PSetSummary]` | Scan model for all unique `IfcPropertySet` names. |
| `get_materials()`      | -              | `List[CountedItem]` | Scan all `IfcMaterial` associations.              |
| **`execute_query()`**  | `ComplexQuery` | `List[str]`         | Recursive GUID filter.                            |
| **`analyze_guids()`**  | `List[str]`    | `SelectionAnalysis` | Data intersection logic.                          |

## 5. Mapping State & Progress DTOs
These models allow the App to show a "Dashboard" or "Progress Bar" of the enrichment work.

```Python
from pydantic import BaseModel
from typing import List, Optional, Any, Dict
from enum import Enum

class MappingState(str, Enum):
    UNMAPPED = "UNMAPPED"         # Element might not match applicability initially (e.g. IfcBuildingElementProxy) and needs type change, or lacks PSets/Attrs
    INCOMPLETE = "INCOMPLETE"     # Required parameters exist, but missing values
    INVALID = "INVALID"           # Required parameters exist, but values violate IDS options/constraints
    COMPLIANT = "COMPLIANT"       # All IDS requirements met exactly

class MappingStatus(BaseModel):
    element_guid: str
    spec_name: str
    state: MappingState
    # Detailed Gaps for the App to resolve
    missing_requirements: List[IdsRequirement] 
    invalid_requirements: List[IdsRequirement] 

class ModelMappingSummary(BaseModel):
    """Overview for the Dashboard."""
    spec_name: str
    total_applicable: int
    compliant_count: int
    invalid_count: int
    incomplete_count: int
    unmapped_count: int
```

---

## 6. Bulk Alignment DTO
To support the "General Match" phase, the user can apply one set of rules to many elements at once.

```Python
class BulkSpecificationManifest(BaseModel):
    """Apply a single set of resolved values to a massive selection."""
    element_guids: List[str]
    specification_name: str
    requirements: List[ConcreteRequirement]
```

---

## 7. The "Enrichment" Workflow Methods

The `IfcStore` must implement these "Alignment" methods:

| **Method**                     | **Input**                   | **Returns**                    | **Implementation Detail**                                                 |
| ------------------------------ | --------------------------- | ------------------------------ | ------------------------------------------------------------------------- |
| **`check_mapping_status()`**   | `ids_store`                 | `List[MappingStatus]`          | **Core Logic:** Compares every element against every applicable IDS Spec. |
| **`get_mapping_summary()`**    | `ids_store`                 | `List[ModelMappingSummary]`    | Aggregates data for the high-level project overview.                      |
| **`apply_bulk_manifest()`**    | `BulkSpecificationManifest` | `List[ModificationResult]`     | Efficiently writes the same data to multiple Express IDs.                 |

---

## 8. Updated Query Engine: "Status Filtering"

The **Query Engine** (`ComplexQuery`) must now support a new category: `MappingStatus`.

- **Filter Category:** `MappingStatus`
    
- **Property Name:** `status` or `spec_name`
    
- **Value:** `UNMAPPED`, `INCOMPLETE`, `INVALID`, `COMPLIANT`.
    
- **Use Case:** User queries `(Category == "IfcWall") AND (MappingStatus == "INCOMPLETE")` to find elements needing granular data.
    

---

## 9. Architectural Guardrails (Mapping Edition)

1. **On-the-Fly Analysis:** Mapping status should be calculated dynamically by comparing the IFC model to the IDS store. Do not rely on hardcoded "Status" properties in the IFC file, as they can become out of sync. All requests must be executed directly against the model with no caching mechanisms, to ensure strict real-time accuracy.

2. **Entity Type Modification (UNMAPPED):** Be prepared that an element may start as generic (e.g. `IfcBuildingElementProxy`) and require its IfcEntity type changed to match applicability before addressing granular properties.

3. **Material Linking:** Both creating new materials and linking them should be supported. Assume the model does not have the right material yet; proactively append it to the document's global `IfcMaterial` library during assignment.

4. **The "Invalid/Incomplete" Logic:** An element is `INCOMPLETE` if required properties exist without values. It is `INVALID` if the current value is not among the `options` (enumerations) allowed by the IDS.

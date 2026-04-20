# IFC-Core

A high-level, Pythonic wrapper for `IfcOpenShell` and `Ifctester`. This library provides a structured, type-safe interface for interacting with BIM data (IFC) and Information Delivery Specifications (IDS) using Pydantic models.

## 🚀 Quick Start

### Prerequisites
- [uv](https://github.com/astral-sh/uv) installed.
- Python 3.11 or higher.

### Installation
```powershell
git clone https://github.com/gernotluidolt/ifc-core.git
cd ifc-core
uv sync
```

## 🛠️ Usage Workflow

The project is designed for a **Decoupled Workflow**: The package identifies requirements and handles the IFC database, while your App handles user decisions and ambiguity resolution.

### 1. Inspecting Requirements (`IdsStore`)
Load an IDS file to see what data is required. The package automatically extracts restrictions like enumerations (options) or ranges.

```python
from ifc_core import IdsStore

ids = IdsStore(Path("requirements.ids"))

# Find a specific rule
spec = ids.get_spec_by_name("WallFireRating")

# Check for allowed values (to build a UI dropdown)
for req in spec.requirements:
    if req.options:
        print(f"User must choose from: {req.options}")
```

### 2. Resolving Ambiguity (The Manifest)
Once your App has gathered user input (e.g., picking "60" from a dropdown of `["30", "60", "90"]`), it creates a `SpecificationManifest`.

```python
from ifc_core import SpecificationManifest, ConcreteRequirement

# Create the contract to hand back to the package
manifest = SpecificationManifest(
    element_guid="1abc...xyz",
    specification_name="WallFireRating",
    requirements=[
        ConcreteRequirement(
            type="Property",
            name="FireRating",
            property_set="Pset_WallCommon",
            value="60"  # The user's resolved choice
        )
    ]
)
```

### 3. Writing to the Model (`IfcStore`)
The `IfcStore` receives the manifest and performs the heavy lifting using the `ifcopenshell.api`.

```python
from ifc_core import IfcStore

ifc = IfcStore(Path("Building.ifc"))

# Apply the resolved manifest
results = ifc.apply_specification(manifest)

for res in results:
    if res.success:
        print(f"Applied: {res.msg}")

ifc.save("Building_Updated.ifc")
```

## 🏗️ Project Structure
```text
src/ifc_core/
├── [ifc_store.py](src/ifc_core/ifc_store.py)       # IFC Entry Point (IfcStore)
├── [ids_store.py](src/ifc_core/ids_store.py)       # IDS Entry Point (IdsStore)
├── [models/](src/ifc_core/models/)            # Pydantic Data Schemas
│   ├── [ifc.py](src/ifc_core/models/ifc.py)         # IFC Metadata & Results
│   └── [ids.py](src/ifc_core/models/ids.py)         # IDS Specs, Requirements & Manifests
└── [services/](src/ifc_core/services/)          # Core Logic Providers
    ├── [metadata.py](src/ifc_core/services/metadata.py)    # IFC Header Parsing
    ├── [writer.py](src/ifc_core/services/writer.py)      # IFC Model Modification (API based)
    ├── [ids_reader.py](src/ifc_core/services/ids_reader.py)  # IDS XML & Restriction Parsing
    ├── [validator.py](src/ifc_core/services/validator.py)   # Gap analysis and mapping validation
    ├── [discovery/](src/ifc_core/services/discovery/)     # Granular spatial/pset/class discovery aggregator
    ├── [inspector.py](src/ifc_core/services/inspector.py)   # Core analytics intersecting common element selections
    └── [query.py](src/ifc_core/services/query.py)       # Native Execution Query Engine solving logic schemas

---
**Detailed Design**: See [TECHNICAL_DESIGN.md](TECHNICAL_DESIGN.md) for class diagrams and service architecture.
```

## 🏗️ Key Capabilities
- **State Engine:** Automatically evaluates the `MappingState` (`COMPLIANT`, `UNMAPPED`, `INCOMPLETE`, `INVALID`) across elements. The current implementation keeps store-local mapping lookup results for repeated queries within the same store instance.
- **Bulk Operations Optimizations:** The internal `ManifestWriter` handles high-frequency assignments resolving complex schemas across thousands of geometries quickly using material memory pooling.
- **Discovery Aggregator:** Drives internal views executing dynamic tree traversals cleanly (creating Virtual Nodes for IFC Classes) across spatial, classification, and material domains.
- **Group Management:** Supports logical element grouping stored in sidecar JSON files, decoupled via `AbstractGroupRepository`.
- **Execution Query System:** Exposes a powerful nested parsing solution tracking objects specifically matching `Material`, `PSet` existence, checking dynamic `MappingStatus`, and recursive algorithms solving logic constraints natively.
- **Ambiguity Management:** Extracts `xs:enumeration` and range restrictions from IDS for UI generation.
- **Contract-Based Writing:** Uses `SpecificationManifest` to ensure the App resolves all choices before the package touches the IFC.
- **Full IDS 1.0 Support:** Handles Properties, Attributes, Materials, and Classifications.
- **Safe Modifications:** Built on top of the official `ifcopenshell.api` to ensure internal IFC data consistency.

## 📘 Public API Contract

### IfcStore Endpoints

| Method | Input | Returns | Purpose |
| --- | --- | --- | --- |
| `info` | - | `ModelMetadata` | File-level schema and author metadata. |
| `save(target_path=None)` | `Path \| None` | `None` | Persists model changes and clears caches. |
| `get_spatial_tree(parent_guid=None)` | `str \| None` | `List[SpatialNode]` | Spatial hierarchy for tree UIs. |
| `get_psets()` | - | `List[PSetSummary]` | Property set inventory with parameter names. |
| `get_materials()` | - | `List[CountedItem]` | Material inventory with usage counts. |
| `analyze_guids(guids)` | `List[str]` | `SelectionAnalysis` | Common and mixed values across selection. |
| `execute_query(query, ids_store=None)` | `ComplexQuery`, `IdsStore \| None` | `List[str]` | Recursive GUID filtering engine. |
| `apply_specification(manifest)` | `SpecificationManifest` | `List[ModificationResult]` | Applies resolved requirements to one element. |
| `apply_bulk_manifest(manifest)` | `BulkSpecificationManifest` | `List[ModificationResult]` | Applies resolved requirements to many elements. |
| `get_groups()` | - | `List[BimGroupSummary]` | List of all logical element groups. |
| `get_group(name)` | `str` | `BimGroup \| None` | Fetch specific group with its GUIDs. |
| `save_group(group)` | `BimGroup` | `bool` | Persist an element group. |
| `check_mapping_status(ids_store)` | `IdsStore` | `List[MappingStatus]` | Per-element IDS compliance states. |
| `get_mapping_summary(ids_store)` | `IdsStore` | `List[ModelMappingSummary]` | Dashboard-level compliance counters. |

### IdsStore Endpoints

| Method | Input | Returns | Purpose |
| --- | --- | --- | --- |
| `specifications` | - | `List[IdsSpecification]` | All specifications parsed from IDS file. |
| `get_spec_by_name(name)` | `str` | `IdsSpecification \| None` | Fast lookup by specification name. |

### Public DTOs

| DTO | Role |
| --- | --- |
| `IdsRequirement` | Parsed IDS facet for applicability and requirements. |
| `IdsSpecification` | One IDS specification with applicability and requirements. |
| `ConcreteRequirement` | App-resolved value assignment unit. |
| `SpecificationManifest` | Single-element write contract for `apply_specification`. |
| `ModelMetadata` | IFC metadata snapshot exposed by `info`. |
| `ModificationResult` | Result object for write operations. |
| `MappingState` | Enum for `UNMAPPED`, `INCOMPLETE`, `INVALID`, `COMPLIANT`. |
| `MappingStatus` | Per element/spec mapping evaluation result. |
| `ModelMappingSummary` | Aggregated mapping counts per spec. |
| `BulkSpecificationManifest` | Multi-element write contract for bulk application. |
| `SpatialNode` | Recursive tree node for discovery views. |
| `CountedItem` | Generic name/count structure. |
| `PSetSummary` | Property set summary with parameter names. |
| `ComparisonOperator` | Operator enum for query filters. |
| `FilterCriterion` | Atomic filter expression in a query tree. |
| `ComplexQuery` | Recursive AND/OR/NOT query contract. |
| `SharedValue` | Shared-or-mixed marker for inspected values. |
| `SelectionAnalysis` | Common attributes/psets across selected GUIDs. |

## 🧪 Tests
The test suite is centered on the public package contract: real IDS parsing, IFC discovery, query execution, and manifest application. It intentionally avoids relying on fake IDS facets or private helper behavior.

## 🧪 Development
```powershell
# Lint and auto-fix (F401, F841, etc.)
uv run ruff check --fix

# Format code
uv run ruff format
```

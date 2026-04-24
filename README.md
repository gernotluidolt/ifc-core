# IFC-Core

**IFC-Core** is a Pythonic wrapper for `IfcOpenShell` and `Ifctester`, engineered to be the core engine behind any IFC-based backend service. It provides a structured, type-safe interface for querying, analyzing, and manipulating BIM data (IFC) and Information Delivery Specifications (IDS) using Pydantic models, with the goal to enrich IFC with the required specifications defined in an IDS file.

## Backend-First Architecture

This library is explicitly designed as a **stateless data engine** to be integrated into server-side applications (e.g., FastAPI, Flask) that serve a separate frontend.

- **Headless & Decoupled:** No UI dependencies. Use it to build APIs that drive your own custom BIM tools.
- **Protocol-First:** All communication is handled via Pydantic DTOs, making it easy to sync with frontend TypeScript types or JSON-based REST APIs.
- **Query & Manipulate:** A powerful recursive query engine for filtering GUIDs and a manifest-based writer for safe IFC modifications.

## Quick Start

### Prerequisites
- [uv](https://github.com/astral-sh/uv) installed.
- Python 3.11 or higher.

### Installation
```powershell
git clone https://github.com/gernotluidolt/ifc-core.git
cd ifc-core
uv sync
```

## Usage Workflow

The project is designed for a **Decoupled Workflow**: The package identifies requirements and handles the IFC database, while your App handles user decisions and ambiguity resolution.

### 1. Inspecting Requirements (`IdsStore`)
Load an IDS file to see what data is required. The package automatically extracts restrictions like enumerations (options) or ranges.

## Frontend Integration

IFC-Core is designed to work in tandem with modern frontend frameworks (Svelte, React, Vue).

1.  **Backend:** Wrap `IfcStore` in an API (e.g., FastAPI).
2.  **Protocol:** Use the provided Pydantic models to define your API response schemas.
3.  **Frontend:** Generate TypeScript types from the models to ensure end-to-end type safety.
4.  **Interaction:** The frontend gathers user input (e.g., property values) and sends a `SpecificationManifest` back to the backend to be applied to the IFC model.

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

## Project Structure
```text
src/ifc_core/
├── [ifc_store.py](src/ifc_core/ifc_store.py)       # IFC Entry Point (IfcStore)
├── [ids_store.py](src/ifc_core/ids_store.py)       # IDS Entry Point (IdsStore)
├── [models/](src/ifc_core/models/)            # Pydantic Data Schemas
│   ├── [ifc.py](src/ifc_core/models/ifc.py)         # IFC Metadata & Results
│   ├── [ids.py](src/ifc_core/models/ids.py)         # IDS Specs & Manifests
│   └── [groups.py](src/ifc_core/models/groups.py)   # Element Group Schemas
├── [services/](src/ifc_core/services/)          # Core Logic Providers
│   ├── [discovery/](src/ifc_core/services/discovery/) # Tree discovery (Spatial, Class, Material)
│   ├── [groups/](src/ifc_core/services/groups/)     # Group persistence repositories
│   ├── [writer.py](src/ifc_core/services/writer.py)      # IFC Model Modification
│   ├── [query.py](src/ifc_core/services/query.py)       # Recursive GUID Query Engine
│   └── [validator.py](src/ifc_core/services/validator.py)   # IDS Mapping Validation
└── [scripts/](src/ifc_core/scripts/)           # Tooling
    └── [generate_types.py](src/ifc_core/scripts/generate_types.py) # TS Type Generator
```

## Key Capabilities
- **State Engine:** Automatically evaluates the `MappingState` (`COMPLIANT`, `UNMAPPED`, `INCOMPLETE`, `INVALID`) across elements.
- **Bulk Operations:** Internal `ManifestWriter` handles high-frequency assignments across thousands of elements using material memory pooling.
- **Deep Discovery:** Unified tree traversals for Spatial Hierarchy, Classification Systems, and Material Associations.
- **Layered Materials:** Specialized support for multi-layered element analysis.
- **Group Management:** Logical element grouping decoupled via `AbstractGroupRepository`.
- **Recursive Query System:** Powerful nested filtering (AND/OR/NOT) for GUIDs based on Attributes, PSets, Materials, or Mapping Status.
- **Frontend Sync:** Includes a script to generate TypeScript interfaces directly from Pydantic DTOs for end-to-end type safety.

## Public API Contract

### IfcStore Endpoints

| Method | Input | Returns | Purpose |
| --- | --- | --- | --- |
| `info` | - | `ModelMetadata` | File-level schema and author metadata. |
| `save(path=None)` | `Path \| None` | `None` | Persists model changes and clears caches. |
| `get_spatial_tree(guid)`| `str \| None` | `List[SpatialNode]` | Spatial hierarchy for tree UIs. |
| `get_classification_tree()`| - | `ClassificationTree` | Full classification tree traversal. |
| `get_psets()` | - | `List[PSetSummary]` | Property set inventory with parameters. |
| `get_materials()` | - | `List[CountedItem]` | Material usage counts. |
| `get_layered_materials()`| - | `LayeredMaterialsSummary`| Multi-layered material analysis. |
| `get_entity_counts()` | - | `List[CountedItem]` | Count of IfcProduct entities by type. |
| `analyze_guids(guids)` | `List[str]` | `SelectionAnalysis` | Intersect values across selection. |
| `execute_query(q, ids)` | `ComplexQuery, ...` | `List[str]` | GUID filtering engine. |
| `apply_specification(m)`| `SpecManifest` | `List[ModResult]` | Apply resolved values to an element. |
| `apply_bulk_manifest(m)`| `BulkManifest` | `List[ModResult]` | Apply resolved values to many elements. |
| `check_mapping_status(ids)`| `IdsStore` | `List[MappingStatus]`| Per-element IDS compliance states. |
| `bind_groups(repo)` | `AbstractGroupRepo`| `None` | Inject group persistence backend. |

### Group Management (`store.groups`)
*Requires binding a repository first via `bind_groups()`.*

| Method | Input | Returns | Purpose |
| --- | --- | --- | --- |
| `get_all()` | - | `List[BimGroupSummary]`| List all available groups. |
| `get_group(name)` | `str` | `BimGroup \| None` | Fetch specific group GUIDs. |
| `save_group(group)` | `BimGroup` | `bool` | Persist an element group. |
| `delete_group(name)`| `str` | `bool` | Remove a group from storage. |

### IdsStore Endpoints

| Method | Input | Returns | Purpose |
| --- | --- | --- | --- |
| `specifications` | - | `List[IdsSpecification]` | All specifications parsed from IDS file. |
| `get_spec_by_name(name)` | `str` | `IdsSpecification \| None` | Lookup by specification name. |

### Public DTOs

| DTO | Role |
| --- | --- |
| `SpecificationManifest` | Write contract for a single element. |
| `BulkSpecificationManifest` | Write contract for multiple elements. |
| `MappingStatus` | Evaluation result for one element/spec. |
| `ModelMappingSummary` | Dashboard-level counters per specification. |
| `SpatialNode` | Recursive node for spatial hierarchies. |
| `ClassificationTree` | Wrapper for hierarchical classification data. |
| `LayeredMaterialsSummary` | Container for multi-layered element counts. |
| `SelectionAnalysis` | Intersected values (mixed vs common) for GUIDs. |
| `BimGroup` | Metadata and GUID list for a logical group. |
| `ComplexQuery` | Boolean logic tree for GUID filtering. |

## Tests
The test suite is centered on the public package contract: real IDS parsing, IFC discovery, query execution, and manifest application. It intentionally avoids relying on fake IDS facets or private helper behavior.

## Development
```powershell
# Lint and auto-fix (F401, F841, etc.)
uv run ruff check --fix

# Format code
uv run ruff format
```

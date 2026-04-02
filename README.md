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
├── store.py           # IFC Entry Point (IfcStore)
├── ids_store.py       # IDS Entry Point (IdsStore)
├── models/            # Pydantic Data Schemas
│   ├── ifc.py         # IFC Metadata & Results
│   └── ids.py         # IDS Specs, Requirements & Manifests
└── services/          # Core Logic Providers
    ├── metadata.py    # IFC Header Parsing
    ├── writer.py      # IFC Model Modification (API based)
    ├── ids_reader.py  # IDS XML & Restriction Parsing
    └── validator.py   # Gap analysis and mapping validation
```

## 🏗️ Key Capabilities
- **State Engine:** Automatically evaluates the `MappingState` (`COMPLIANT`, `UNMAPPED`, `INCOMPLETE`, `INVALID`) across elements natively leveraging scoped query caching.
- **Bulk Operations Optimizations:** The internal `ManifestWriter` handles high-frequency assignments resolving complex schemas across thousands of geometries quickly using material memory pooling.
- **Ambiguity Management:** Extracts `xs:enumeration` and range restrictions from IDS for UI generation.
- **Contract-Based Writing:** Uses `SpecificationManifest` to ensure the App resolves all choices before the package touches the IFC.
- **Full IDS 1.0 Support:** Handles Properties, Attributes, Materials, and Classifications.
- **Safe Modifications:** Built on top of the official `ifcopenshell.api` to ensure internal IFC data consistency.

## 🧪 Development
```powershell
# Lint and auto-fix (F401, F841, etc.)
uv run ruff check --fix

# Format code
uv run ruff format
```

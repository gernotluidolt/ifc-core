# IFC-Core

A high-level, Pythonic wrapper for `IfcOpenShell` and `Ifctester`. This library provides a structured, type-safe interface for interacting with BIM data (IFC) and Information Delivery Specifications (IDS) using Pydantic models.

## 🚀 Quick Start

### Prerequisites
- [uv](https://github.com/astral-sh/uv) installed.
- Python 3.11 or higher.

### Installation
```powershell
git clone [https://github.com/gernotluidolt/ifc-core.git](https://github.com/gernotluidolt/ifc-core.git)
cd ifc-core
uv sync
```

## 🛠️ Usage

### 1. Working with IFC Models (`IfcStore`)
The `IfcStore` manages the IFC file lifecycle and provides clean access to model metadata and modification tools.

```python
from pathlib import Path
from ifc_core import IfcStore

# Load a model
store = IfcStore(Path(r"C:\Models\BMW.ifc"))

# Read Metadata (via Pydantic)
print(f"Author: {store.info.author}")
print(f"Schema: {store.info.schema_version}")

# Add a Property Set to an element
result = store.add_custom_data(
    guid="1abc...xyz",
    pset_name="Digital_Twin_Data",
    data={"IsVerified": True, "Version": 1.1}
)

if result.success:
    store.save()
```

### 2. Working with IDS Requirements (`IdsStore`)
The `IdsStore` parses IDS XML files into a list of "Specification" objects, allowing you to inspect requirements independently of a model.

```python
from ifc_core import IdsStore

# Load the IDS
ids = IdsStore(Path("requirements.ids"))

# Inspect specifications
for spec in ids.specifications:
    print(f"Requirement: {spec.name}")
    print(f"Applies to: {[f.type for f in spec.applicability]}")
    
    for req in spec.requirements:
        print(f" - Must have {req.type}: {req.name} = {req.value}")
```

## 🏗️ Project Structure
The project uses a **Service-Layer Pattern** to keep logic decoupled and scalable.

```text
src/ifc_core/
├── store.py           # IFC Entry Point (IfcStore)
├── ids_store.py       # IDS Entry Point (IdsStore)
├── models/            # Pydantic Data Schemas
│   ├── ifc.py         # IFC Metadata & Results
│   └── ids.py         # IDS Specs & Facets
└── services/          # Core Logic Providers
    ├── metadata.py    # IFC Header Parsing
    ├── writer.py      # IFC Model Modification
    └── ids_reader.py  # IDS XML Parsing
```

## 🧪 Development
```powershell
# Quality Control
uv run ruff check --fix
uv run ruff format
```

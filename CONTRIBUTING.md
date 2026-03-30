# 📑 IFC-Core (BIM Data Wrapper)

## 🎯 Project Vision
A professional-grade Python wrapper for `IfcOpenShell` and `Ifctester`. It uses a **Decoupled Architecture** where the core logic handles IFC/IDS complexity and communicates with external Applications (UIs) via strict **Pydantic Models**.

## 🏗️ Technical Stack
- **Environment:** `uv` (Astral) for dependency and project management.
- **BIM Core:** `ifcopenshell`, `ifctester`.
- **Data Validation:** `pydantic` (v2) for all "Contract" objects.
- **Quality:** `ruff` for linting and formatting.

## 📂 Project Structure (Service-Layer Pattern)
```text
src/ifc_core/
├── ifc_store.py       # Entry point for .ifc files (IfcStore class)
├── ids_store.py       # Entry point for .ids files (IdsStore class)
├── models/
│   ├── ifc.py         # IFC Metadata, ModificationResult
│   └── ids.py         # IdsSpecification, SpecificationManifest, ConcreteRequirement
└── services/
    ├── ids_reader.py  # IDS 1.0 parser (extracts enumerations/options/ranges)
    ├── writer.py      # ifcopenshell.api wrapper for PSets/Attributes
    ├── aligner.py     # Logic to apply Manifests to elements
    └── metadata.py    # IFC Header/Schema extraction
```

## 🔄 The "Manifest" Workflow
We have established a strict boundary to prevent "guesswork" in the package:
1. **IdsStore** provides an `IdsSpecification` containing `options` (e.g., `["Internal", "External"]`).
2. **The App** (UI) handles the user's choice to resolve ambiguities.
3. **The App** sends back a **`SpecificationManifest`** (a list of `ConcreteRequirement` objects).
4. **IfcStore** receives this manifest and executes the `ifcopenshell.api` commands to update the model.

## 📍 Current State & Quality
- **Linter Status:** `ruff check` is clean. 
- **Path Handling:** Uses `pathlib` and handles Windows raw strings `r"C:\..."`.
- **Boilerplate:** All core classes, services, and models are initialized and wired through `__init__.py`.

## 🚀 Next Steps for the Agent
1. **Validation Logic:** Build a service to check if an element already matches a `Specification` (Gap Analysis).
2. **Classification/Material Support:** Expand `writer.py` and `aligner.py` to handle IFC Classifications and Materials.
3. **Unit Testing:** Add `pytest` for the `ids_reader` to ensure XML restrictions are correctly mapped to Pydantic options.
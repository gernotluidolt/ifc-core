import pytest
from pathlib import Path
import ifcopenshell
import ifcopenshell.api

from ifc_core import IfcStore, IdsStore


@pytest.fixture(scope="session")
def real_ids_path():
    return Path(
        "tests/data/AT_3-1_Informationsanforderungskatalog für Hochbauprojekte_edited.ids"
    )


@pytest.fixture(scope="session")
def real_ifc_path():
    return Path("tests/data/HG_TWPL_TW_033.ifc")


@pytest.fixture(scope="session")
def real_ids_store(real_ids_path):
    return IdsStore(real_ids_path)


@pytest.fixture(scope="session")
def real_ifc_store(real_ifc_path):
    # Loaded once per session for reading
    return IfcStore(real_ifc_path)


@pytest.fixture
def mock_ifc_store(tmp_path):
    # 1. Create a blank IFC4 model
    model = ifcopenshell.file(schema="IFC4")

    # Setup project with context to avoid geometric errors
    project = ifcopenshell.api.run(
        "root.create_entity", model, ifc_class="IfcProject", name="Sample Project"
    )
    ifcopenshell.api.run("unit.assign_unit", model)

    # Define the spatial hierarchy
    site = ifcopenshell.api.run(
        "root.create_entity", model, ifc_class="IfcSite", name="My Site"
    )
    building = ifcopenshell.api.run(
        "root.create_entity", model, ifc_class="IfcBuilding", name="My Building"
    )
    storey = ifcopenshell.api.run(
        "root.create_entity", model, ifc_class="IfcBuildingStorey", name="Ground Floor"
    )

    ifcopenshell.api.run(
        "aggregate.assign_object", model, products=[site], relating_object=project
    )
    ifcopenshell.api.run(
        "aggregate.assign_object", model, products=[building], relating_object=site
    )
    ifcopenshell.api.run(
        "aggregate.assign_object", model, products=[storey], relating_object=building
    )

    # 3. Create a Wall
    wall = ifcopenshell.api.run(
        "root.create_entity", model, ifc_class="IfcWall", name="Sample Wall"
    )

    # Some basic geometric context if missing
    contexts = model.by_type("IfcGeometricRepresentationContext")
    if not contexts:
        context_rc = ifcopenshell.api.run(
            "context.add_context", model, context_type="Model"
        )
        context = ifcopenshell.api.run(
            "context.add_context",
            model,
            context_type="Model",
            context_identifier="Body",
            target_view="MODEL_VIEW",
            parent=context_rc,
        )
    else:
        context = contexts[0]

    representation_wall = ifcopenshell.api.run(
        "geometry.add_wall_representation",
        model,
        context=context,
        length=5.0,
        thickness=0.2,
        height=3.0,
    )
    ifcopenshell.api.run(
        "geometry.assign_representation",
        model,
        product=wall,
        representation=representation_wall,
    )
    ifcopenshell.api.run("geometry.edit_object_placement", model, product=wall)

    # 4. Create a Slab
    slab = ifcopenshell.api.run(
        "root.create_entity", model, ifc_class="IfcSlab", name="Sample Slab"
    )
    representation_slab = ifcopenshell.api.run(
        "geometry.add_slab_representation",
        model,
        context=context,
        depth=0.2,
        polyline=[(0.0, 0.0), (5.0, 0.0), (5.0, 5.0), (0.0, 5.0), (0.0, 0.0)],
    )
    ifcopenshell.api.run(
        "geometry.assign_representation",
        model,
        product=slab,
        representation=representation_slab,
    )
    ifcopenshell.api.run("geometry.edit_object_placement", model, product=slab)

    # 5. Assign Wall and Slab to the Ground Floor
    ifcopenshell.api.run(
        "spatial.assign_container", model, products=[wall], relating_structure=storey
    )
    ifcopenshell.api.run(
        "spatial.assign_container", model, products=[slab], relating_structure=storey
    )

    # 6. Save the file
    path = tmp_path / "sample_model.ifc"
    model.write(str(path))

    return IfcStore(path)

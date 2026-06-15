import ifcopenshell
from ifc_core.models.ids import ConcreteRequirement
from ifc_core.models.ifc import BulkSpecificationManifest


def test_entity_swapping(mock_ifc_store):
    elements = mock_ifc_store._model.by_type("IfcSlab")
    guid = elements[0].GlobalId

    manifest = BulkSpecificationManifest(
        element_guids=[guid],
        specification_name="SwapSpec",
        requirements=[
            ConcreteRequirement(type="Entity", name="Entity", value="IfcWall")
        ],
    )

    results = mock_ifc_store.apply_bulk_manifest(manifest)
    assert all(r.success for r in results)

    reloaded = mock_ifc_store._model.by_guid(guid)
    assert reloaded.is_a("IfcWall")

    # Swap back
    manifest.requirements[0].value = "IfcSlab"
    mock_ifc_store.apply_bulk_manifest(manifest)

    reloaded2 = mock_ifc_store._model.by_guid(guid)
    assert reloaded2.is_a("IfcSlab")


def test_intelligent_pset_injection(mock_ifc_store):
    elements = mock_ifc_store._model.by_type("IfcWall")
    guid = elements[0].GlobalId

    # Inject property twice verifying container doesn't duplicate
    manifest = BulkSpecificationManifest(
        element_guids=[guid],
        specification_name="PropSpec",
        requirements=[
            ConcreteRequirement(
                type="Property",
                name="LoadBearing",
                property_set="Pset_WallCommon",
                value="True",
            )
        ],
    )

    mock_ifc_store.apply_bulk_manifest(manifest)
    mock_ifc_store.apply_bulk_manifest(manifest)

    wall = mock_ifc_store._model.by_guid(guid)
    all_psets = [
        rel.RelatingPropertyDefinition
        for rel in wall.IsDefinedBy
        if rel.is_a("IfcRelDefinesByProperties")
    ]
    wall_commons = [p for p in all_psets if p.Name == "Pset_WallCommon"]
    assert len(wall_commons) == 1

    # Verify the property itself was set properly
    for prop in wall_commons[0].HasProperties:
        if prop.Name == "LoadBearing":
            assert str(prop.NominalValue.wrappedValue) == "True"


def test_datatype_casting(mock_ifc_store):
    elements = mock_ifc_store._model.by_type("IfcWall")
    guid = elements[0].GlobalId

    manifest = BulkSpecificationManifest(
        element_guids=[guid],
        specification_name="CastSpec",
        requirements=[
            ConcreteRequirement(
                type="Property",
                name="LoadBearing",
                property_set="Pset_WallCommon",
                value="True",
                data_type="boolean",
            ),
            ConcreteRequirement(
                type="Property",
                name="SomeInt",
                property_set="Pset_WallCommon",
                value="42",
                data_type="integer",
            ),
            ConcreteRequirement(
                type="Property",
                name="SomeFloat",
                property_set="Pset_WallCommon",
                value="123.45",
                data_type="decimal",
            ),
        ],
    )

    mock_ifc_store.apply_bulk_manifest(manifest)

    wall = mock_ifc_store._model.by_guid(guid)
    all_psets = [
        rel.RelatingPropertyDefinition
        for rel in wall.IsDefinedBy
        if rel.is_a("IfcRelDefinesByProperties")
    ]
    wall_commons = [p for p in all_psets if p.Name == "Pset_WallCommon"]
    assert len(wall_commons) == 1

    props = {p.Name: p for p in wall_commons[0].HasProperties}
    assert props["LoadBearing"].NominalValue.is_a("IfcBoolean")
    assert props["LoadBearing"].NominalValue.wrappedValue is True
    assert props["SomeInt"].NominalValue.is_a("IfcInteger")
    assert props["SomeInt"].NominalValue.wrappedValue == 42
    assert props["SomeFloat"].NominalValue.is_a("IfcReal")
    assert props["SomeFloat"].NominalValue.wrappedValue == 123.45


def test_associates_material_classification_partof(mock_ifc_store):
    elements = mock_ifc_store._model.by_type("IfcWall")
    guid = elements[0].GlobalId

    # Create a test storey in mock model so partof relation can find it
    storey = mock_ifc_store._model.create_entity(
        "IfcBuildingStorey",
        GlobalId=ifcopenshell.guid.new(),
        Name="TestStorey"
    )

    manifest = BulkSpecificationManifest(
        element_guids=[guid],
        specification_name="RelationSpec",
        requirements=[
            ConcreteRequirement(
                type="Material",
                name="Material",
                value="TestConcrete",
            ),
            ConcreteRequirement(
                type="Classification",
                name="DSR_System",
                value="SfB LG-07-02-01",
            ),
            ConcreteRequirement(
                type="PartOf",
                name="IFCBUILDINGSTOREY",
                value="TestStorey",
                relation="IFCRELCONTAINEDINSPATIALSTRUCTURE",
            ),
        ],
    )

    results = mock_ifc_store.apply_bulk_manifest(manifest)
    assert all(r.success for r in results)

    wall = mock_ifc_store._model.by_guid(guid)

    # Verify material association relation
    mats = [
        rel.RelatingMaterial
        for rel in getattr(wall, "HasAssociations", [])
        if rel.is_a("IfcRelAssociatesMaterial")
    ]
    assert any(getattr(m, "Name", "") == "TestConcrete" for m in mats)

    # Verify classification association relation
    classifications = [
        rel.RelatingClassification
        for rel in getattr(wall, "HasAssociations", [])
        if rel.is_a("IfcRelAssociatesClassification")
    ]
    assert len(classifications) == 1
    assert classifications[0].Identification == "SfB LG-07-02-01"
    assert classifications[0].ReferencedSource.Name == "DSR_System"

    # Verify containment relation
    containments = [
        rel.RelatingStructure
        for rel in getattr(wall, "ContainedInStructure", [])
        if rel.is_a("IfcRelContainedInSpatialStructure")
    ]
    assert len(containments) == 1
    assert containments[0].Name == "TestStorey"

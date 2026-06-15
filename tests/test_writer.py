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


def test_dynamic_relations_and_core_attributes(mock_ifc_store):
    from ifc_core.services.inspector import analyze_guids
    from ifc_core.models.ids import ConcreteRequirement
    from ifc_core.models.ifc import BulkSpecificationManifest

    elements = mock_ifc_store._model.by_type("IfcWall")
    guid = elements[0].GlobalId

    # Pre-set some native attributes on the element
    wall = mock_ifc_store._model.by_guid(guid)
    wall.Tag = "TestTag123"
    wall.Description = "TestDescription"

    # 1. Verify inspector reads native attributes dynamically (Tag, Description, etc.)
    analysis = analyze_guids(mock_ifc_store._model, [guid])
    assert "Tag" in analysis.common_attributes
    assert analysis.common_attributes["Tag"].value == "TestTag123"
    assert "Description" in analysis.common_attributes
    assert analysis.common_attributes["Description"].value == "TestDescription"

    # 2. Test dynamic material creation (Oak Wood) and old association removal
    # First, make sure Oak Wood doesn't exist
    assert not any(m.Name == "Oak Wood" for m in mock_ifc_store._model.by_type("IfcMaterial"))

    manifest = BulkSpecificationManifest(
        element_guids=[guid],
        specification_name="OakSpec",
        requirements=[
            ConcreteRequirement(
                type="Material",
                name="Material",
                value="Oak Wood",
            )
        ]
    )

    results = mock_ifc_store.apply_bulk_manifest(manifest)
    assert all(r.success for r in results)

    # Oak Wood should exist now
    materials = mock_ifc_store._model.by_type("IfcMaterial")
    oak = next((m for m in materials if m.Name == "Oak Wood"), None)
    assert oak is not None

    # Check relation
    wall = mock_ifc_store._model.by_guid(guid)
    mats = [
        rel.RelatingMaterial
        for rel in getattr(wall, "HasAssociations", [])
        if rel.is_a("IfcRelAssociatesMaterial")
    ]
    # Old material (TestConcrete) should be gone, only Oak Wood is linked
    assert len(mats) == 1
    assert mats[0].Name == "Oak Wood"

    # 3. Test dynamic storey creation (Roof Storey) and aggregation
    # First, make sure Roof Storey doesn't exist
    assert not any(s.Name == "Roof Storey" for s in mock_ifc_store._model.by_type("IfcBuildingStorey"))

    # Find or create building to host it in hierarchy
    building = next(iter(mock_ifc_store._model.by_type("IfcBuilding")), None)
    if not building:
        building = mock_ifc_store._model.create_entity(
            "IfcBuilding",
            GlobalId=ifcopenshell.guid.new(),
            Name="TestBuilding"
        )

    manifest_storey = BulkSpecificationManifest(
        element_guids=[guid],
        specification_name="StoreySpec",
        requirements=[
            ConcreteRequirement(
                type="PartOf",
                name="IFCBUILDINGSTOREY",
                value="Roof Storey",
                relation="IFCRELCONTAINEDINSPATIALSTRUCTURE",
            )
        ]
    )

    results_storey = mock_ifc_store.apply_bulk_manifest(manifest_storey)
    assert all(r.success for r in results_storey)

    # Roof Storey should exist now
    storeys = mock_ifc_store._model.by_type("IfcBuildingStorey")
    roof = next((s for s in storeys if s.Name == "Roof Storey"), None)
    assert roof is not None

    # Containment relation check
    wall = mock_ifc_store._model.by_guid(guid)
    containments = [
        rel.RelatingStructure
        for rel in getattr(wall, "ContainedInStructure", [])
        if rel.is_a("IfcRelContainedInSpatialStructure")
    ]
    assert len(containments) == 1
    assert containments[0].Name == "Roof Storey"

    # Check aggregation relation to building
    aggregates = mock_ifc_store._model.by_type("IfcRelAggregates")
    b_agg = next((r for r in aggregates if r.RelatingObject == building), None)
    assert b_agg is not None
    assert roof in b_agg.RelatedObjects

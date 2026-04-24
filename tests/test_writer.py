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

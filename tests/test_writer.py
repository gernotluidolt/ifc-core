from ifc_core.models.ifc import BulkSpecificationManifest
from ifc_core.models.ids import ConcreteRequirement, SpecificationManifest
from ifc_core.services.writer import ManifestWriter, apply_manifest_to_element

def test_entity_swapping(mock_ifc_store):
    elements = mock_ifc_store._model.by_type("IfcSlab")
    assert len(elements) == 1
    guid = elements[0].GlobalId
    
    manifest = BulkSpecificationManifest(
        element_guids=[guid],
        specification_name="SwapSpec",
        requirements=[
            ConcreteRequirement(type="Entity", name="Entity", value="IfcWall")
        ]
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
            ConcreteRequirement(type="Property", name="LoadBearing", property_set="Pset_WallCommon", value="True")
        ]
    )
    
    mock_ifc_store.apply_bulk_manifest(manifest)
    mock_ifc_store.apply_bulk_manifest(manifest)
    
    wall = mock_ifc_store._model.by_guid(guid)
    all_psets = [rel.RelatingPropertyDefinition for rel in wall.IsDefinedBy if rel.is_a("IfcRelDefinesByProperties")]
    wall_commons = [p for p in all_psets if p.Name == "Pset_WallCommon"]
    assert len(wall_commons) == 1
    
    # Verify the property itself was set properly
    for prop in wall_commons[0].HasProperties:
        if prop.Name == "LoadBearing":
            assert str(prop.NominalValue.wrappedValue) == "True"


def test_manifest_writer_material_cache_deduplicates(mock_ifc_store):
    writer = ManifestWriter(mock_ifc_store._model)

    first = writer._get_or_create_material("Concrete")
    second = writer._get_or_create_material("Concrete")

    materials = [m for m in mock_ifc_store._model.by_type("IfcMaterial") if m.Name == "Concrete"]
    assert first == second
    assert len(materials) == 1


def test_manifest_writer_apply_requirement_unsupported_type(mock_ifc_store):
    writer = ManifestWriter(mock_ifc_store._model)
    wall = mock_ifc_store._model.by_type("IfcWall")[0]

    req = ConcreteRequirement(type="Unsupported", name="X", value="Y")
    result = writer.apply_requirement(wall, req)

    assert not result.success
    assert "Unsupported req type" in result.msg


def test_manifest_writer_apply_requirement_returns_error_on_exception(monkeypatch, mock_ifc_store):
    writer = ManifestWriter(mock_ifc_store._model)
    wall = mock_ifc_store._model.by_type("IfcWall")[0]

    def _raise(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("ifcopenshell.api.run", _raise)

    req = ConcreteRequirement(type="Attribute", name="Name", value="Changed")
    result = writer.apply_requirement(wall, req)

    assert not result.success
    assert "Error in Name" in result.msg


def test_apply_manifest_guid_not_found_and_bulk_missing_guid(mock_ifc_store):
    class _FakeModel:
        def by_guid(self, _guid):
            return None

    writer = ManifestWriter(_FakeModel())

    manifest = SpecificationManifest(
        element_guid="NO_SUCH_GUID",
        specification_name="Missing",
        requirements=[ConcreteRequirement(type="Attribute", name="Name", value="X")],
    )
    single_results = writer.apply_manifest(manifest)
    assert len(single_results) == 1
    assert not single_results[0].success

    bulk = BulkSpecificationManifest(
        element_guids=["NO_SUCH_GUID"],
        specification_name="MissingBulk",
        requirements=[ConcreteRequirement(type="Attribute", name="Name", value="X")],
    )
    bulk_results = writer.apply_bulk_manifest(bulk)
    assert len(bulk_results) == 1
    assert not bulk_results[0].success


def test_apply_manifest_to_element_helper_path(mock_ifc_store):
    wall = mock_ifc_store._model.by_type("IfcWall")[0]
    manifest = SpecificationManifest(
        element_guid=wall.GlobalId,
        specification_name="AttrSpec",
        requirements=[ConcreteRequirement(type="Attribute", name="Name", value="Renamed Wall")],
    )

    results = apply_manifest_to_element(mock_ifc_store._model, manifest)
    assert all(r.success for r in results)

    changed = mock_ifc_store._model.by_guid(wall.GlobalId)
    assert changed.Name == "Renamed Wall"

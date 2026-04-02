
from ifc_core import IfcStore
from ifc_core.models.ifc import MappingState, MappingStatus, ModificationResult
from ifc_core.models.ids import ConcreteRequirement, IdsSpecification, SpecificationManifest


class _DummyIdsStore:
    def __init__(self, specs):
        self.specifications = specs


def test_ifc_store_init_raises_for_missing_file(tmp_path):
    missing = tmp_path / "missing.ifc"

    try:
        IfcStore(missing)
        assert False, "Expected FileNotFoundError"
    except FileNotFoundError:
        assert True


def test_ifc_store_save_writes_target_and_clears_cache(mock_ifc_store, tmp_path):
    mock_ifc_store._mapping_cache["x"] = "y"
    out = tmp_path / "saved.ifc"

    mock_ifc_store.save(out)

    assert out.exists()
    assert mock_ifc_store._mapping_cache == {}


def test_ifc_store_apply_specification_delegates_and_clears_cache(monkeypatch, mock_ifc_store):
    wall = mock_ifc_store._model.by_type("IfcWall")[0]
    mock_ifc_store._mapping_cache["seed"] = "value"

    captured = {"called": False}

    def _fake_apply(model, manifest):
        captured["called"] = True
        assert model == mock_ifc_store._model
        assert manifest.element_guid == wall.GlobalId
        return [ModificationResult(success=True, msg="ok")]

    monkeypatch.setattr("ifc_core.ifc_store.apply_manifest_to_element", _fake_apply)

    manifest = SpecificationManifest(
        element_guid=wall.GlobalId,
        specification_name="Spec",
        requirements=[ConcreteRequirement(type="Attribute", name="Name", value="Changed")],
    )

    results = mock_ifc_store.apply_specification(manifest)
    assert captured["called"]
    assert mock_ifc_store._mapping_cache == {}
    assert results[0].success


def test_ifc_store_apply_bulk_manifest_delegates_and_clears_cache(monkeypatch, mock_ifc_store):
    wall = mock_ifc_store._model.by_type("IfcWall")[0]
    mock_ifc_store._mapping_cache["seed"] = "value"

    class _FakeWriter:
        def __init__(self, model):
            assert model == mock_ifc_store._model

        def apply_bulk_manifest(self, manifest):
            assert manifest.element_guids == [wall.GlobalId]
            return [ModificationResult(success=True, msg="bulk")]

    monkeypatch.setattr("ifc_core.ifc_store.ManifestWriter", _FakeWriter)

    from ifc_core.models.ifc import BulkSpecificationManifest

    manifest = BulkSpecificationManifest(
        element_guids=[wall.GlobalId],
        specification_name="Bulk",
        requirements=[ConcreteRequirement(type="Attribute", name="Name", value="Changed")],
    )

    results = mock_ifc_store.apply_bulk_manifest(manifest)
    assert mock_ifc_store._mapping_cache == {}
    assert results[0].success


def test_ifc_store_check_mapping_status_uses_cache(monkeypatch, mock_ifc_store):
    wall = mock_ifc_store._model.by_type("IfcWall")[0]
    slab = mock_ifc_store._model.by_type("IfcSlab")[0]

    spec = IdsSpecification(name="AnySpec", applicability=[], requirements=[])
    ids_store = _DummyIdsStore([spec])

    calls = {"n": 0}

    def _fake_validate(element, _spec):
        calls["n"] += 1
        return MappingStatus(
            element_guid=element.GlobalId,
            spec_name=_spec.name,
            state=MappingState.COMPLIANT,
            missing_requirements=[],
            invalid_requirements=[],
        )

    monkeypatch.setattr("ifc_core.ifc_store.validate_mapping_status", _fake_validate)

    class _NoGuidElement:
        pass

    original_by_type = mock_ifc_store._model.by_type

    def _by_type_with_missing_guid(type_name):
        if type_name == "IfcProduct":
            return [_NoGuidElement(), *original_by_type(type_name)]
        return original_by_type(type_name)

    monkeypatch.setattr(mock_ifc_store._model, "by_type", _by_type_with_missing_guid)

    first = mock_ifc_store.check_mapping_status(ids_store)
    second = mock_ifc_store.check_mapping_status(ids_store)

    assert len(first) >= 2
    assert len(second) >= 2
    assert calls["n"] == len(first)
    assert any(s.element_guid == wall.GlobalId for s in first)
    assert any(s.element_guid == slab.GlobalId for s in first)


def test_ifc_store_get_mapping_summary_counts_states_and_ignores_unknown_spec(monkeypatch, mock_ifc_store):
    spec = IdsSpecification(name="SpecA", applicability=[], requirements=[])
    ids_store = _DummyIdsStore([spec])

    statuses = [
        MappingStatus(element_guid="1", spec_name="SpecA", state=MappingState.COMPLIANT),
        MappingStatus(element_guid="2", spec_name="SpecA", state=MappingState.INVALID),
        MappingStatus(element_guid="3", spec_name="SpecA", state=MappingState.INCOMPLETE),
        MappingStatus(element_guid="4", spec_name="SpecA", state=MappingState.UNMAPPED),
        MappingStatus(element_guid="x", spec_name="OtherSpec", state=MappingState.COMPLIANT),
    ]

    monkeypatch.setattr(mock_ifc_store, "check_mapping_status", lambda _ids: statuses)

    summary = mock_ifc_store.get_mapping_summary(ids_store)
    assert len(summary) == 1
    row = summary[0]
    assert row.spec_name == "SpecA"
    assert row.total_applicable == 4
    assert row.compliant_count == 1
    assert row.invalid_count == 1
    assert row.incomplete_count == 1
    assert row.unmapped_count == 1


def test_ifc_store_info_property_uses_metadata_service(monkeypatch, mock_ifc_store):
    class _Meta:
        schema_version = "IFC4"
        author = "test"

    monkeypatch.setattr("ifc_core.ifc_store.get_model_info", lambda model: _Meta())

    info = mock_ifc_store.info
    assert info.schema_version == "IFC4"
    assert info.author == "test"

import ifctester.ids

from ifc_core.services.ids_reader import _map_facet_to_requirement, parse_ids_file


def test_map_entity_facet_from_real_ids(real_ids_path):
    ids_data = ifctester.ids.open(str(real_ids_path))
    facet = ids_data.specifications[0].applicability[0]

    req = _map_facet_to_requirement(facet)

    assert req.type == "entity"
    assert req.value is not None
    assert req.options == []
    assert req.min_inclusive is None
    assert req.max_inclusive is None


def test_map_property_facet_from_real_ids(real_ids_path):
    ids_data = ifctester.ids.open(str(real_ids_path))
    facet = ids_data.specifications[0].requirements[0]

    req = _map_facet_to_requirement(facet)

    assert req.type == "property"
    assert req.name is not None
    assert req.property_set is not None


def test_parse_ids_file_with_real_ids(real_ids_path):
    specs = parse_ids_file(real_ids_path)

    assert len(specs) > 0
    assert all(spec.name for spec in specs)
    assert any(spec.applicability for spec in specs)
    assert any(spec.requirements for spec in specs)

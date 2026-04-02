import ifctester.ids

from ifc_core.services.ids_reader import _map_facet_to_requirement, parse_ids_file


class _FacetWithoutIsA:
    def __init__(self):
        self.baseName = "Height"
        self.propertySet = "Pset_Demo"
        self.value = {"enumeration": ["1", 2], "minInclusive": "1.5", "maxInclusive": 3}


class _RestrictionObj:
    enumeration = ["A", "B"]
    minInclusive = 10
    maxInclusive = 20


class _FacetWithObjectRestriction:
    def __init__(self):
        self.name = "Status"
        self.property_set = "Pset_Status"
        self.value = "A"
        self.restriction = _RestrictionObj()


class _EntityFacet:
    def __init__(self):
        self.name = "IfcWall"
        self.value = None

    def is_a(self):
        return "Entity"


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


def test_map_facet_without_is_a_uses_class_name_and_dict_restriction():
    req = _map_facet_to_requirement(_FacetWithoutIsA())

    assert req.type == "_facetwithoutisa"
    assert req.name == "Height"
    assert req.property_set == "Pset_Demo"
    assert req.value is None
    assert req.options == ["1", "2"]
    assert req.min_inclusive == 1.5
    assert req.max_inclusive == 3.0


def test_map_facet_with_object_restriction_and_entity_raw_value_fallback():
    req = _map_facet_to_requirement(_FacetWithObjectRestriction())
    assert req.type == "_facetwithobjectrestriction"
    assert req.options == ["A", "B"]
    assert req.min_inclusive == 10.0
    assert req.max_inclusive == 20.0

    entity_req = _map_facet_to_requirement(_EntityFacet())
    assert entity_req.type == "entity"
    assert entity_req.value == "IfcWall"

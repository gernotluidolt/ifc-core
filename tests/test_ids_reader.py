from unittest.mock import patch, MagicMock

from ifc_core.services.ids_reader import _map_facet_to_requirement, parse_ids_file


class MockRestriction:
    def __init__(self, enumeration=None, minInclusive=None, maxInclusive=None):
        if enumeration is not None:
            self.enumeration = enumeration
        if minInclusive is not None:
            self.minInclusive = minInclusive
        if maxInclusive is not None:
            self.maxInclusive = maxInclusive


class MockFacet:
    def __init__(self, type_str, name=None, value=None, property_set=None, restriction=None):
        self._type_str = type_str
        self.name = name
        self.value = value
        self.property_set = property_set
        
        if restriction is not None:
            self.restriction = restriction
            
    def is_a(self):
        return self._type_str


def test_map_facet_with_enumeration():
    res = MockRestriction(enumeration=["Existing", "New"])
    facet = MockFacet(type_str="property", name="Status", property_set="Pset_WallCommon", restriction=res)
    
    req = _map_facet_to_requirement(facet)
    
    assert req.type == "property"
    assert req.name == "Status"
    assert req.property_set == "Pset_WallCommon"
    assert req.options == ["Existing", "New"]
    assert req.min_inclusive is None
    assert req.max_inclusive is None


def test_map_facet_with_range():
    res = MockRestriction(minInclusive=1.5, maxInclusive=5.0)
    facet = MockFacet(type_str="property", name="Length", restriction=res)
    
    req = _map_facet_to_requirement(facet)
    
    assert req.name == "Length"
    assert req.options == []
    assert req.min_inclusive == 1.5
    assert req.max_inclusive == 5.0


def test_map_facet_no_restriction():
    facet = MockFacet(type_str="entity", value="IfcWall")
    
    req = _map_facet_to_requirement(facet)
    
    assert req.type == "entity"
    assert req.value == "IfcWall"
    assert req.options == []
    assert req.min_inclusive is None

@patch('ifctester.ids.open')
def test_parse_ids_file(mock_ids_open):
    # Mocking ifctester.ids.open return object
    mock_ids_data = MagicMock()
    
    mock_spec = MagicMock()
    mock_spec.name = "MySpec"
    mock_spec.identifier = "SPEC-001"
    mock_spec.description = "Test"
    mock_spec.instructions = "Instructions"
    mock_spec.min_occurs = 1
    mock_spec.max_occurs = "unbounded"
    
    # Set up applicability
    app_facet = MockFacet(type_str="entity", name="IfcWall")
    mock_spec.applicability = [app_facet]
    
    # Set up requirements
    req_res = MockRestriction(enumeration=["True", "False"])
    req_facet = MockFacet(type_str="property", name="LoadBearing", property_set="Pset_WallCommon", restriction=req_res)
    mock_spec.requirements = [req_facet]
    
    mock_ids_data.specifications = [mock_spec]
    mock_ids_open.return_value = mock_ids_data
    
    specs = parse_ids_file("dummy_path.ids")
    
    assert len(specs) == 1
    spec = specs[0]
    assert spec.name == "MySpec"
    assert len(spec.applicability) == 1
    assert spec.applicability[0].type == "entity"
    
    assert len(spec.requirements) == 1
    assert spec.requirements[0].options == ["True", "False"]

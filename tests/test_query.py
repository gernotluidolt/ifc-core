import ifcopenshell.api

from ifc_core.models.ifc import ComplexQuery, FilterCriterion, ComparisonOperator
from ifc_core.models.ids import IdsRequirement, IdsSpecification
from ifc_core.services.query import QueryEngine


class _DummyIdsStore:
    def __init__(self, specifications):
        self.specifications = specifications


def test_query_pset_existence(real_ifc_store):
    query = ComplexQuery(
        logical_op="AND",
        criteria=[
            FilterCriterion(
                category="PSet",
                operator=ComparisonOperator.EQUALS,  # Operator doesn't matter for mere existence check if name is omitted
                value=None,
                property_set="Pset_WallCommon",
            )
        ],
    )
    results = real_ifc_store.execute_query(query)
    assert isinstance(results, list)


def test_query_nested_and_or_contains(mock_ifc_store):
    wall = mock_ifc_store._model.by_type("IfcWall")[0]
    slab = mock_ifc_store._model.by_type("IfcSlab")[0]

    pset = ifcopenshell.api.run(
        "pset.add_pset", mock_ifc_store._model, product=wall, name="Pset_WallCommon"
    )
    ifcopenshell.api.run(
        "pset.edit_pset",
        mock_ifc_store._model,
        pset=pset,
        properties={"IsExternal": True},
    )

    query = ComplexQuery(
        logical_op="AND",
        criteria=[
            FilterCriterion(
                category="Attribute",
                name="Name",
                operator=ComparisonOperator.CONTAINS,
                value="Sample",
            ),
            ComplexQuery(
                logical_op="OR",
                criteria=[
                    FilterCriterion(
                        category="PSet",
                        name="IsExternal",
                        property_set="Pset_WallCommon",
                        operator=ComparisonOperator.EQUALS,
                        value="True",
                    ),
                    FilterCriterion(
                        category="Attribute",
                        name="Name",
                        operator=ComparisonOperator.EQUALS,
                        value="NotARealElement",
                    ),
                ],
            ),
        ],
    )

    results = mock_ifc_store.execute_query(query)
    assert wall.GlobalId in results
    assert slab.GlobalId not in results


def test_query_not_excludes_matching_entities(mock_ifc_store):
    wall = mock_ifc_store._model.by_type("IfcWall")[0]
    slab = mock_ifc_store._model.by_type("IfcSlab")[0]

    query = ComplexQuery(
        logical_op="NOT",
        criteria=[
            FilterCriterion(
                category="Attribute",
                name="Name",
                operator=ComparisonOperator.CONTAINS,
                value="Wall",
            )
        ],
    )

    results = mock_ifc_store.execute_query(query)
    assert wall.GlobalId not in results
    assert slab.GlobalId in results


def test_query_story_and_material(mock_ifc_store):
    wall = mock_ifc_store._model.by_type("IfcWall")[0]

    concrete = ifcopenshell.api.run(
        "material.add_material", mock_ifc_store._model, name="Concrete"
    )
    ifcopenshell.api.run(
        "material.assign_material",
        mock_ifc_store._model,
        products=[wall],
        type="IfcMaterial",
        material=concrete,
    )

    query = ComplexQuery(
        logical_op="AND",
        criteria=[
            FilterCriterion(
                category="Story",
                operator=ComparisonOperator.EQUALS,
                value="Ground Floor",
            ),
            FilterCriterion(
                category="Material",
                operator=ComparisonOperator.EQUALS,
                value="Concrete",
            ),
        ],
    )

    results = mock_ifc_store.execute_query(query)
    assert wall.GlobalId in results


def test_query_mapping_status_uses_cache(monkeypatch, mock_ifc_store):
    spec = IdsSpecification(
        name="WallApplicability",
        applicability=[IdsRequirement(type="entity", name="IfcWall")],
        requirements=[],
    )

    call_count = {"n": 0}
    from ifc_core.services.validator import check_mapping_status as _original_check

    def _tracked_check_mapping_status(element, _spec):
        call_count["n"] += 1
        return _original_check(element, _spec)

    monkeypatch.setattr(
        "ifc_core.services.validator.check_mapping_status",
        _tracked_check_mapping_status,
    )

    query = ComplexQuery(
        logical_op="AND",
        criteria=[
            FilterCriterion(
                category="MappingStatus",
                operator=ComparisonOperator.EQUALS,
                value="COMPLIANT",
                property_set="WallApplicability",
            )
        ],
    )

    ids_store = _DummyIdsStore([spec])
    first = mock_ifc_store.execute_query(query, ids_store=ids_store)
    first_count = call_count["n"]
    second = mock_ifc_store.execute_query(query, ids_store=ids_store)

    wall = mock_ifc_store._model.by_type("IfcWall")[0]
    assert wall.GlobalId in first
    assert wall.GlobalId in second
    assert first_count > 0
    assert call_count["n"] == first_count


def test_query_engine_compare_numeric_and_invalid_operator(mock_ifc_store):
    engine = QueryEngine(mock_ifc_store._model)

    assert engine._compare("10", "2", ComparisonOperator.GREATER_THAN)
    assert engine._compare("2", "10", ComparisonOperator.LESS_THAN)
    assert engine._compare("A", "B", ComparisonOperator.NOT_EQUALS)

    invalid_query = ComplexQuery(
        logical_op="XOR",
        criteria=[
            FilterCriterion(
                category="Attribute",
                name="Name",
                operator=ComparisonOperator.EQUALS,
                value="Sample Wall",
            )
        ],
    )
    wall = mock_ifc_store._model.by_type("IfcWall")[0]
    assert engine._evaluate_node(wall, invalid_query) is False


def test_query_pset_container_existence_true_and_false(mock_ifc_store):
    wall = mock_ifc_store._model.by_type("IfcWall")[0]
    pset = ifcopenshell.api.run(
        "pset.add_pset", mock_ifc_store._model, product=wall, name="Pset_WallCommon"
    )
    ifcopenshell.api.run(
        "pset.edit_pset",
        mock_ifc_store._model,
        pset=pset,
        properties={"Reference": "W-01"},
    )

    exists = ComplexQuery(
        logical_op="AND",
        criteria=[
            FilterCriterion(
                category="PSet",
                operator=ComparisonOperator.EQUALS,
                value=None,
                property_set="Pset_WallCommon",
            )
        ],
    )
    missing = ComplexQuery(
        logical_op="AND",
        criteria=[
            FilterCriterion(
                category="PSet",
                operator=ComparisonOperator.EQUALS,
                value=None,
                property_set="Pset_DoesNotExist",
            )
        ],
    )

    assert wall.GlobalId in mock_ifc_store.execute_query(exists)
    assert wall.GlobalId not in mock_ifc_store.execute_query(missing)


def test_analyze_guids(real_ifc_store):
    guids_to_check = []
    for wall in real_ifc_store._model.by_type("IfcWall")[:3]:
        if getattr(wall, "GlobalId", None):
            guids_to_check.append(wall.GlobalId)

    if len(guids_to_check) >= 2:
        analysis = real_ifc_store.analyze_guids(guids_to_check)
        assert hasattr(analysis, "common_attributes")
        assert hasattr(analysis, "common_psets")

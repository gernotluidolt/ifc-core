import ifcopenshell.api

from ifc_core.models.ifc import ComplexQuery, FilterCriterion, ComparisonOperator
from ifc_core.models.ifc import MappingState


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
    wall_name_fragment = wall.Name.split(":")[0]

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
                value=wall_name_fragment,
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
    wall_name_fragment = wall.Name.split(":")[0]

    query = ComplexQuery(
        logical_op="NOT",
        criteria=[
            FilterCriterion(
                category="Attribute",
                name="Name",
                operator=ComparisonOperator.CONTAINS,
                value=wall_name_fragment,
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
                value="00_EG",
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


def test_query_mapping_status_returns_matching_entities(real_ifc_store, real_ids_store):
    statuses = real_ifc_store.check_mapping_status(real_ids_store)
    candidate = next(
        status for status in statuses if status.state == MappingState.INCOMPLETE
    )

    query = ComplexQuery(
        logical_op="AND",
        criteria=[
            FilterCriterion(
                category="MappingStatus",
                operator=ComparisonOperator.EQUALS,
                value=MappingState.INCOMPLETE.value,
                property_set=candidate.spec_name,
            )
        ],
    )

    results = real_ifc_store.execute_query(query, ids_store=real_ids_store)
    assert candidate.element_guid in results
    assert results


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

import ifcopenshell.api

from ifc_core.models.ifc import (
    ComparisonOperator,
    ComplexQuery,
    FilterCriterion,
    MappingState,
)


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


def test_query_classification_matching(mock_ifc_store):
    wall = mock_ifc_store._model.by_type("IfcWall")[0]
    guid = wall.GlobalId

    # Create classification reference and relate it to the wall
    classification = mock_ifc_store._model.create_entity(
        "IfcClassification", Name="DSR_System", Source="IDS Specification"
    )
    classification_reference = mock_ifc_store._model.create_entity(
        "IfcClassificationReference",
        Identification="SfB LG-07-02-01",
        Name="SpecialWallClassification",
        ReferencedSource=classification,
    )
    mock_ifc_store._model.create_entity(
        "IfcRelAssociatesClassification",
        GlobalId=ifcopenshell.guid.new(),
        RelatingClassification=classification_reference,
        RelatedObjects=[wall],
    )

    # 1. Query by classification code/Identification
    query_code = ComplexQuery(
        logical_op="AND",
        criteria=[
            FilterCriterion(
                category="Classification",
                operator=ComparisonOperator.EQUALS,
                value="SfB LG-07-02-01",
            )
        ],
    )
    results = mock_ifc_store.execute_query(query_code)
    assert guid in results

    # 2. Query by classification reference name
    query_name = ComplexQuery(
        logical_op="AND",
        criteria=[
            FilterCriterion(
                category="Classification",
                operator=ComparisonOperator.EQUALS,
                value="SpecialWallClassification",
            )
        ],
    )
    results = mock_ifc_store.execute_query(query_name)
    assert guid in results

    # 3. Query by classification system name and code
    query_system_and_code = ComplexQuery(
        logical_op="AND",
        criteria=[
            FilterCriterion(
                category="Classification",
                property_set="DSR_System",
                operator=ComparisonOperator.EQUALS,
                value="SfB LG-07-02-01",
            )
        ],
    )
    results = mock_ifc_store.execute_query(query_system_and_code)
    assert guid in results

    # 4. Query by classification system name only (value is True)
    query_system_only = ComplexQuery(
        logical_op="AND",
        criteria=[
            FilterCriterion(
                category="Classification",
                property_set="DSR_System",
                operator=ComparisonOperator.EQUALS,
                value=True,
            )
        ],
    )
    results = mock_ifc_store.execute_query(query_system_only)
    assert guid in results

    # 5. Query by combined classification reference code and name
    query_combined = ComplexQuery(
        logical_op="AND",
        criteria=[
            FilterCriterion(
                category="Classification",
                property_set="DSR_System",
                operator=ComparisonOperator.EQUALS,
                value="SfB LG-07-02-01 SpecialWallClassification",
            )
        ],
    )
    results = mock_ifc_store.execute_query(query_combined)
    assert guid in results


def test_query_new_operators_and_categories(mock_ifc_store):
    wall = mock_ifc_store._model.by_type("IfcWall")[0]
    guid = wall.GlobalId

    # 1. Attribute filtering with StartsWith & EndsWith (case-insensitive)
    wall.Name = "TestWallElement"
    
    # 2. Add an IfcElementQuantity
    q_set = mock_ifc_store._model.create_entity("IfcElementQuantity", Name="BaseQuantities")
    qty_length = mock_ifc_store._model.create_entity("IfcQuantityLength", Name="Length", LengthValue=12.5)
    qty_volume = mock_ifc_store._model.create_entity("IfcQuantityVolume", Name="NetVolume", VolumeValue=45.2)
    q_set.Quantities = [qty_length, qty_volume]
    mock_ifc_store._model.create_entity(
        "IfcRelDefinesByProperties",
        GlobalId=ifcopenshell.guid.new(),
        RelatingPropertyDefinition=q_set,
        RelatedObjects=[wall]
    )

    # Starts with (case insensitive)
    query_starts = ComplexQuery(
        logical_op="AND",
        criteria=[
            FilterCriterion(
                category="Attribute",
                name="Name",
                operator=ComparisonOperator.STARTS_WITH,
                value="testwall",
            )
        ]
    )
    assert guid in mock_ifc_store.execute_query(query_starts)

    # Ends with (case insensitive)
    query_ends = ComplexQuery(
        logical_op="AND",
        criteria=[
            FilterCriterion(
                category="Attribute",
                name="Name",
                operator=ComparisonOperator.ENDS_WITH,
                value="element",
            )
        ]
    )
    assert guid in mock_ifc_store.execute_query(query_ends)

    # Quantity numeric comparison >=
    query_qty_gte = ComplexQuery(
        logical_op="AND",
        criteria=[
            FilterCriterion(
                category="Quantity",
                name="Length",
                operator=ComparisonOperator.GREATER_THAN_EQUALS,
                value=12.0,
            )
        ]
    )
    assert guid in mock_ifc_store.execute_query(query_qty_gte)

    # Quantity numeric comparison <=
    query_qty_lte = ComplexQuery(
        logical_op="AND",
        criteria=[
            FilterCriterion(
                category="Quantity",
                name="NetVolume",
                operator=ComparisonOperator.LESS_THAN_EQUALS,
                value="45.2",
            )
        ]
    )
    assert guid in mock_ifc_store.execute_query(query_qty_lte)




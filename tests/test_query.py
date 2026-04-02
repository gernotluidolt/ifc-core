from ifc_core.models.ifc import ComplexQuery, FilterCriterion, ComparisonOperator

def test_query_pset_existence(real_ifc_store):
    query = ComplexQuery(
        logical_op="AND",
        criteria=[
            FilterCriterion(
                category="PSet",
                operator=ComparisonOperator.EQUALS, # Operator doesn't matter for mere existence check if name is omitted
                value=None, 
                property_set="Pset_WallCommon"
            )
        ]
    )
    results = real_ifc_store.execute_query(query)
    assert isinstance(results, list)

def test_analyze_guids(real_ifc_store):
    guids_to_check = []
    for wall in real_ifc_store._model.by_type("IfcWall")[:3]:
        if getattr(wall, "GlobalId", None):
            guids_to_check.append(wall.GlobalId)
            
    if len(guids_to_check) >= 2:
        analysis = real_ifc_store.analyze_guids(guids_to_check)
        assert hasattr(analysis, "common_attributes")
        assert hasattr(analysis, "common_psets")

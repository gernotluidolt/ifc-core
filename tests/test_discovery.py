def test_get_spatial_tree(real_ifc_store):
    sites = real_ifc_store.get_spatial_tree(parent_guid=None)
    assert len(sites) > 0
    
    # Traverse down to test Virtual Node generation 
    # Site -> Building -> Storey
    first_site = sites[0]
    buildings = real_ifc_store.get_spatial_tree(parent_guid=first_site.guid)
    
    storeys = []
    for b in buildings:
        storeys.extend(real_ifc_store.get_spatial_tree(parent_guid=b.guid))
        
    for s in storeys:
        if s.type == "IfcBuildingStorey":
            virtual_nodes = real_ifc_store.get_spatial_tree(parent_guid=s.guid)
            for v in virtual_nodes:
                # Based on the user requirement, virutal nodes look like <parent_guid>:<ifc_class>
                assert ":" in v.guid 
                assert v.has_children is False
                assert v.element_count > 0

def test_get_psets(real_ifc_store):
    psets = real_ifc_store.get_psets()
    assert len(psets) > 0
    
def test_get_materials(real_ifc_store):
    mats = real_ifc_store.get_materials()
    assert len(mats) > 0

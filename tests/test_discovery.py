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


def test_get_entity_counts_grouped(real_ifc_store):
    counts = real_ifc_store.get_entity_counts()
    assert isinstance(counts, dict)
    assert "all" in counts
    assert "building" in counts
    assert "finishing_furniture" in counts
    assert "distribution" in counts
    
    # Each list should contain CountedItem elements
    for cat in ("all", "building", "finishing_furniture", "distribution"):
        assert isinstance(counts[cat], list)
        for item in counts[cat]:
            assert hasattr(item, "name")
            assert hasattr(item, "element_count")


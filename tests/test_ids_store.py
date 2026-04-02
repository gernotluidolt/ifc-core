def test_real_ids_store(real_ids_store):
    assert len(real_ids_store.specifications) > 0
    for spec in real_ids_store.specifications:
        assert spec.name
        
    spec = real_ids_store.specifications[0]
    assert hasattr(spec, "applicability")
    assert hasattr(spec, "requirements")

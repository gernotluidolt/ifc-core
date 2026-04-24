def ref_id(ref_entity) -> str:
    return (
        getattr(ref_entity, "Identification", None)
        or getattr(ref_entity, "Name", None)
        or getattr(ref_entity, "ItemReference", None)
        or str(ref_entity.id())
    )


def resolve_system_name(obj) -> str | None:
    if not obj:
        return None
    if obj.is_a("IfcClassification"):
        return getattr(obj, "Name", None) or "Unknown System"
    if hasattr(obj, "ReferencedSource"):
        return resolve_system_name(getattr(obj, "ReferencedSource", None))
    return None


def get_contained_elements(parent) -> list:
    elements = []
    # Elements that are spatially decomposed from this parent
    for rel in getattr(parent, "IsDecomposedBy", []):
        if hasattr(rel, "RelatedObjects"):
            elements.extend(rel.RelatedObjects)

    # Elements contained spatially
    for rel in getattr(parent, "ContainsElements", []):
        if hasattr(rel, "RelatedElements"):
            elements.extend(rel.RelatedElements)

    return elements

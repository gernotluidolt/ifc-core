from collections import defaultdict

import ifcopenshell

from ..models.ifc import (
    ClassificationNode,
    ClassificationTree,
    CountedItem,
    LayeredMaterialItem,
    LayeredMaterialsSummary,
    PSetSummary,
    SpatialNode,
)


def _ref_id(ref_entity) -> str:
    return (
        getattr(ref_entity, "Identification", None)
        or getattr(ref_entity, "Name", None)
        or getattr(ref_entity, "ItemReference", None)
        or str(ref_entity.id())
    )


def _resolve_system_name(obj) -> str | None:
    if not obj:
        return None
    if obj.is_a("IfcClassification"):
        return getattr(obj, "Name", None) or "Unknown System"
    if hasattr(obj, "ReferencedSource"):
        return _resolve_system_name(getattr(obj, "ReferencedSource", None))
    return None


def _get_contained_elements(parent) -> list:
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


def get_spatial_tree(
    model: ifcopenshell.file, parent_guid: str | None = None
) -> list[SpatialNode]:
    nodes = []

    if parent_guid is None:
        sites = model.by_type("IfcSite")
        if not sites:
            sites = model.by_type("IfcBuilding")

        for site in sites:
            children = _get_contained_elements(site)
            nodes.append(
                SpatialNode(
                    guid=site.GlobalId,
                    name=getattr(site, "Name", "") or "Unnamed",
                    type=site.is_a(),
                    element_count=len(children),
                    has_children=len(children) > 0,
                    children=None,
                )
            )
        return nodes

    parent = model.by_guid(parent_guid)
    if not parent:
        return []

    if parent.is_a("IfcBuildingStorey"):
        elements = _get_contained_elements(parent)
        class_counts = defaultdict(int)
        for el in elements:
            class_counts[el.is_a()] += 1

        for ifc_type, count in class_counts.items():
            nodes.append(
                SpatialNode(
                    guid=f"{parent.GlobalId}:{ifc_type}",
                    name=ifc_type,
                    type=ifc_type,
                    element_count=count,
                    has_children=False,
                    children=None,
                )
            )
        return nodes

    children = _get_contained_elements(parent)
    for child in children:
        child_elements = _get_contained_elements(child)
        nodes.append(
            SpatialNode(
                guid=child.GlobalId,
                name=getattr(child, "Name", "") or "Unnamed",
                type=child.is_a(),
                element_count=len(child_elements),
                has_children=len(child_elements) > 0,
                children=None,
            )
        )

    return nodes


def get_psets(model: ifcopenshell.file) -> list[PSetSummary]:
    pset_map = defaultdict(set)
    pset_counts = defaultdict(int)

    for rel in model.by_type("IfcRelDefinesByProperties"):
        pset = rel.RelatingPropertyDefinition
        if not pset or not pset.is_a("IfcPropertySet"):
            continue

        name = getattr(pset, "Name", "") or "Unnamed"

        objects = getattr(rel, "RelatedObjects", [])
        pset_counts[name] += len(objects)

        for prop in getattr(pset, "HasProperties", []):
            prop_name = getattr(prop, "Name", "") or "Unnamed"
            pset_map[name].add(prop_name)

    return [
        PSetSummary(name=name, element_count=pset_counts[name], parameters=list(params))
        for name, params in pset_map.items()
    ]


def get_materials(model: ifcopenshell.file) -> list[CountedItem]:
    mat_counts = defaultdict(int)

    for rel in model.by_type("IfcRelAssociatesMaterial"):
        mat = rel.RelatingMaterial
        if not mat:
            continue

        name = getattr(mat, "Name", "") or "Unnamed"
        if mat.is_a("IfcMaterialLayerSetUsage"):
            mset = getattr(mat, "ForLayerSet", None)
            if mset:
                name = getattr(mset, "MaterialSetName", name)

        objects = getattr(rel, "RelatedObjects", [])
        mat_counts[name] += len(objects)

    return [CountedItem(name=k, element_count=v) for k, v in mat_counts.items()]


def get_entity_counts(model: ifcopenshell.file) -> list[CountedItem]:
    entity_counts = defaultdict(int)
    for element in model.by_type("IfcProduct"):
        try:
            entity_counts[element.is_a()] += 1
        except Exception:
            continue

    return [
        CountedItem(name=name, element_count=count)
        for name, count in sorted(entity_counts.items(), key=lambda x: x[0])
    ]


def get_classification_tree(model: ifcopenshell.file) -> ClassificationTree:
    systems: dict[str, dict] = {}
    ref_nodes: dict[int, dict] = {}

    for classification in model.by_type("IfcClassification"):
        sys_name = getattr(classification, "Name", None) or "Unknown System"
        systems[sys_name] = {
            "type": "system",
            "name": sys_name,
            "id": f"sys::{sys_name}",
            "children": [],
            "_ifc_id": classification.id(),
        }

    for ref in model.by_type("IfcClassificationReference"):
        rid = _ref_id(ref)
        ref_label = (
            f"{rid} {ref.Name}"
            if getattr(ref, "Name", None) and getattr(ref, "Name", None) != rid
            else rid
        )
        ref_nodes[ref.id()] = {
            "type": "reference",
            "name": ref_label,
            "id": f"ref::{ref.id()}",
            "children": [],
            "_obj": ref,
        }

    for node in ref_nodes.values():
        ref = node.get("_obj")
        source = getattr(ref, "ReferencedSource", None)
        if not source:
            continue

        if source.is_a("IfcClassification"):
            sys_name = getattr(source, "Name", None) or "Unknown System"
            if sys_name in systems:
                systems[sys_name]["children"].append(node)
        elif source.is_a("IfcClassificationReference") and source.id() in ref_nodes:
            ref_nodes[source.id()]["children"].append(node)

    classified_elements = set()
    for rel in model.by_type("IfcRelAssociatesClassification"):
        target = getattr(rel, "RelatingClassification", None)
        if not target:
            continue

        target_node = None
        if target.is_a("IfcClassificationReference"):
            target_node = ref_nodes.get(target.id())
        elif target.is_a("IfcClassification"):
            sys_name = getattr(target, "Name", None)
            if sys_name:
                target_node = systems.get(sys_name)

        if not target_node:
            continue

        for elem in getattr(rel, "RelatedObjects", []) or []:
            if getattr(elem, "is_a", lambda: "")() == "IfcProject":
                continue

            name = getattr(elem, "Name", None) or getattr(elem, "GlobalId", None)
            if not name:
                continue

            classified_elements.add(name)
            target_node["children"].append(
                {
                    "type": "element",
                    "name": str(name),
                    "id": f"el::{elem.id()}",
                    "children": [],
                }
            )

    all_named_elements = set()
    for product in model.by_type("IfcProduct"):
        if getattr(product, "is_a", lambda: "")() == "IfcProject":
            continue
        name = getattr(product, "Name", None) or getattr(product, "GlobalId", None)
        if name:
            all_named_elements.add(str(name))

    unclassified = sorted(all_named_elements - classified_elements)
    if unclassified:
        systems["(unclassified)"] = {
            "type": "system",
            "name": "(unclassified)",
            "id": "sys::unclassified",
            "children": [
                {"type": "element", "name": name, "id": f"el::{name}", "children": []}
                for name in unclassified
            ],
        }

    def _normalize(node: dict) -> dict:
        children = node.get("children", [])
        children.sort(key=lambda x: (x.get("type") == "element", x.get("name", "")))
        out = {
            "id": str(node.get("id") or ""),
            "type": str(node.get("type") or "reference"),
            "name": str(node.get("name") or ""),
            "children": [_normalize(child) for child in children],
        }
        if "count" in node and node.get("count") is not None:
            out["count"] = int(node["count"])
        return out

    tree_nodes = []
    for _, sys_node in sorted(systems.items(), key=lambda kv: kv[0]):
        sys_node["count"] = len(sys_node.get("children", []))
        tree_nodes.append(ClassificationNode.model_validate(_normalize(sys_node)))

    return ClassificationTree(tree=tree_nodes, total_elements=len(all_named_elements))


def get_layered_materials(model: ifcopenshell.file) -> LayeredMaterialsSummary:
    material_element_count: dict[str, int] = defaultdict(int)
    material_layer_count: dict[str, int] = defaultdict(int)
    layered_total = 0

    for rel in model.by_type("IfcRelAssociatesMaterial"):
        mat = getattr(rel, "RelatingMaterial", None)
        if not mat or not mat.is_a("IfcMaterialLayerSetUsage"):
            continue

        layer_set = getattr(mat, "ForLayerSet", None)
        layers = (
            list(getattr(layer_set, "MaterialLayers", []) or []) if layer_set else []
        )
        if len(layers) <= 1:
            continue

        layered_total += len(getattr(rel, "RelatedObjects", []) or [])

        for layer in layers:
            material = getattr(layer, "Material", None)
            if not material:
                continue
            name = getattr(material, "Name", None) or "Unnamed"
            material_element_count[name] += len(
                getattr(rel, "RelatedObjects", []) or []
            )
            material_layer_count[name] += 1

    items = [
        LayeredMaterialItem(
            name=str(name),
            element_count=int(material_element_count[name]),
            layer_count=int(material_layer_count[name]),
        )
        for name in sorted(material_element_count.keys())
    ]

    return LayeredMaterialsSummary(materials=items, total_elements=layered_total)

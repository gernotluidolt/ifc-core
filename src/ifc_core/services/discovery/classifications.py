import ifcopenshell
from ...models.ifc import ClassificationNode, ClassificationTree
from .utils import ref_id, resolve_system_name

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
        rid = ref_id(ref)
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
        else:
            sys_name = None
            
        if sys_name and not target_node:
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
                    "guid": str(getattr(elem, "GlobalId", None) or ""),
                    "children": [],
                }
            )

    all_named_elements = set()
    product_guid_map = {}
    for product in model.by_type("IfcProduct"):
        if getattr(product, "is_a", lambda: "")() == "IfcProject":
            continue
        name = getattr(product, "Name", None) or getattr(product, "GlobalId", None)
        if name:
            name_str = str(name)
            all_named_elements.add(name_str)
            product_guid_map[name_str] = getattr(product, "GlobalId", None)

    unclassified = sorted(all_named_elements - classified_elements)
    if unclassified:
        systems["(unclassified)"] = {
            "type": "system",
            "name": "(unclassified)",
            "id": "sys::unclassified",
            "children": [
                {
                    "type": "element",
                    "name": name,
                    "id": f"el::{name}",
                    "guid": str(product_guid_map.get(name) or ""),
                    "children": [],
                }
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
        if "guid" in node:
            out["guid"] = str(node.get("guid") or "")
        if "count" in node and node.get("count") is not None:
            out["count"] = int(node["count"])
        return out

    tree_nodes = []
    for _, sys_node in sorted(systems.items(), key=lambda kv: kv[0]):
        sys_node["count"] = len(sys_node.get("children", []))
        tree_nodes.append(ClassificationNode.model_validate(_normalize(sys_node)))

    return ClassificationTree(tree=tree_nodes, total_elements=len(all_named_elements))

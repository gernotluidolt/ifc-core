from collections import defaultdict
import ifcopenshell
from ...models.ifc import (
    CountedItem,
    LayeredMaterialItem,
    LayeredMaterialsSummary
)

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

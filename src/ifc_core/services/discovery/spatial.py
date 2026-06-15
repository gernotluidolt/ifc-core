from collections import defaultdict
import ifcopenshell
from ...models.ifc import SpatialNode, CountedItem
from .utils import get_contained_elements

def get_spatial_tree(
    model: ifcopenshell.file, parent_guid: str | None = None
) -> list[SpatialNode]:
    """Helper to build a deep spatial tree recursively."""

    def build_node(item) -> SpatialNode:
        children = get_contained_elements(item)

        # If it's a storey, we group elements by type as children
        if item.is_a("IfcBuildingStorey"):
            type_counts = defaultdict(int)
            for el in children:
                type_counts[el.is_a()] += 1

            type_nodes = [
                SpatialNode(
                    guid=f"{item.GlobalId}:{t}",
                    name=t,
                    type=t,
                    element_count=c,
                    has_children=False,
                    children=[],
                )
                for t, c in sorted(type_counts.items())
            ]
            
            return SpatialNode(
                guid=item.GlobalId,
                name=getattr(item, "Name", "") or "Unnamed Storey",
                type=item.is_a(),
                element_count=len(children),
                has_children=len(type_nodes) > 0,
                children=type_nodes,
            )

        # Standard recursive step for Site/Building
        child_nodes = [build_node(c) for c in children if c.is_a("IfcSpatialElement")]
        
        return SpatialNode(
            guid=item.GlobalId,
            name=getattr(item, "Name", "") or "Unnamed",
            type=item.is_a(),
            element_count=len(children),
            has_children=len(child_nodes) > 0,
            children=child_nodes,
        )

    # If parent_guid is provided, we still support lazy fetch for API compatibility
    if parent_guid is not None:
        parent = model.by_guid(parent_guid)
        if not parent:
            return []
        
        if parent.is_a("IfcBuildingStorey"):
            elements = get_contained_elements(parent)
            class_counts = defaultdict(int)
            for el in elements:
                class_counts[el.is_a()] += 1
            return [
                SpatialNode(
                    guid=f"{parent.GlobalId}:{t}",
                    name=t, type=t, element_count=c, has_children=False, children=None
                )
                for t, c in sorted(class_counts.items())
            ]
        
        children = get_contained_elements(parent)
        return [
            SpatialNode(
                guid=c.GlobalId,
                name=getattr(c, "Name", "") or "Unnamed",
                type=c.is_a(),
                element_count=len(get_contained_elements(c)),
                has_children=len(get_contained_elements(c)) > 0,
                children=None
            )
            for c in children if c.is_a("IfcSpatialElement")
        ]

    # Default: Return deep tree from the root(s)
    roots = model.by_type("IfcSite") or model.by_type("IfcBuilding")
    return [build_node(r) for r in roots]


def get_entity_counts(model: ifcopenshell.file) -> dict[str, list[CountedItem]]:
    entity_counts = defaultdict(int)
    for element in model.by_type("IfcProduct"):
        try:
            entity_counts[element.is_a()] += 1
        except Exception:
            continue

    # Class inheritance categorization parent lists
    building_parents = ["IfcBuildingElement"]
    finishing_parents = [
        "IfcFurniture",
        "IfcSystemFurnitureElement",
        "IfcWindow",
        "IfcDoor",
        "IfcStair",
        "IfcRailing",
    ]
    distribution_parents = ["IfcDistributionElement"]

    type_categories = {}
    grouped = {
        "all": [],
        "building": [],
        "finishing_furniture": [],
        "distribution": [],
    }

    for name, count in sorted(entity_counts.items(), key=lambda x: x[0]):
        item = CountedItem(name=name, element_count=count)
        grouped["all"].append(item)

        if name not in type_categories:
            try:
                temp_el = model.create_entity(name)
                if any(temp_el.is_a(p) for p in building_parents):
                    type_categories[name] = "building"
                elif any(temp_el.is_a(p) for p in finishing_parents):
                    type_categories[name] = "finishing_furniture"
                elif any(temp_el.is_a(p) for p in distribution_parents):
                    type_categories[name] = "distribution"
                else:
                    type_categories[name] = None
                model.remove(temp_el)
            except Exception:
                type_categories[name] = None

        cat = type_categories[name]
        if cat:
            grouped[cat].append(item)

    return grouped


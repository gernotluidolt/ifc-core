import ifcopenshell
from collections import defaultdict
from typing import Optional, List
from ..models.ifc import SpatialNode, CountedItem, PSetSummary

def _get_contained_elements(parent) -> List:
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

def get_spatial_tree(model: ifcopenshell.file, parent_guid: Optional[str] = None) -> List[SpatialNode]:
    nodes = []
    
    if parent_guid is None:
        sites = model.by_type("IfcSite")
        if not sites:
            sites = model.by_type("IfcBuilding")
            
        for site in sites:
            children = _get_contained_elements(site)
            nodes.append(SpatialNode(
                guid=site.GlobalId,
                name=getattr(site, "Name", "") or "Unnamed",
                type=site.is_a(),
                element_count=len(children),
                has_children=len(children) > 0,
                children=None
            ))
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
            nodes.append(SpatialNode(
                guid=f"{parent.GlobalId}:{ifc_type}",
                name=ifc_type,
                type=ifc_type,
                element_count=count,
                has_children=False,
                children=None
            ))
        return nodes

    children = _get_contained_elements(parent)
    for child in children:
        child_elements = _get_contained_elements(child)
        nodes.append(SpatialNode(
            guid=child.GlobalId,
            name=getattr(child, "Name", "") or "Unnamed",
            type=child.is_a(),
            element_count=len(child_elements),
            has_children=len(child_elements) > 0,
            children=None
        ))
        
    return nodes

def get_psets(model: ifcopenshell.file) -> List[PSetSummary]:
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
        PSetSummary(
            name=name,
            element_count=pset_counts[name],
            parameters=list(params)
        )
        for name, params in pset_map.items()
    ]

def get_materials(model: ifcopenshell.file) -> List[CountedItem]:
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
        
    return [
        CountedItem(name=k, element_count=v)
        for k, v in mat_counts.items()
    ]

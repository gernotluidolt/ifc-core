import ifcopenshell
import ifcopenshell.util.element
from typing import List
from ..models.ifc import SelectionAnalysis, SharedValue

def analyze_guids(model: ifcopenshell.file, guids: List[str]) -> SelectionAnalysis:
    if not guids:
        return SelectionAnalysis(common_attributes={}, common_psets={})
        
    elements = [model.by_guid(g) for g in guids if getattr(model, "by_guid", None) and model.by_guid(g)]
    # filter out Nones
    elements = [e for e in elements if e is not None]
    
    if not elements:
        return SelectionAnalysis(common_attributes={}, common_psets={})

    # Intersect attributes
    infos = [e.get_info() for e in elements]
    
    common_attr_keys = set(infos[0].keys())
    for info in infos[1:]:
        common_attr_keys.intersection_update(info.keys())
        
    common_attributes = {}
    for key in common_attr_keys:
        if key in ("id", "type", "GlobalId"): 
            continue
        val1 = infos[0][key]
        is_mixed = any(info[key] != val1 for info in infos[1:])
        
        if is_mixed:
            common_attributes[key] = SharedValue(value="<Mixed>", is_mixed=True)
        else:
            common_attributes[key] = SharedValue(value=val1, is_mixed=False)

    # Intersect Psets
    all_psets = [ifcopenshell.util.element.get_psets(e) for e in elements]
    common_pset_names = set(all_psets[0].keys())
    for pset in all_psets[1:]:
        common_pset_names.intersection_update(pset.keys())
        
    common_psets = {}
    for pset_name in common_pset_names:
        common_prop_names = set(all_psets[0][pset_name].keys())
        for psets in all_psets[1:]:
            common_prop_names.intersection_update(psets[pset_name].keys())
            
        common_psets[pset_name] = {}
        for prop in common_prop_names:
            if prop in ("id", "type"): 
                continue
            val1 = all_psets[0][pset_name][prop]
            is_mixed = any(psets[pset_name][prop] != val1 for psets in all_psets[1:])
            
            if is_mixed:
                common_psets[pset_name][prop] = SharedValue(value="<Mixed>", is_mixed=True)
            else:
                common_psets[pset_name][prop] = SharedValue(value=val1, is_mixed=False)
                
    return SelectionAnalysis(
        common_attributes=common_attributes,
        common_psets=common_psets
    )

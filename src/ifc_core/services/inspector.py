
import ifcopenshell
import ifcopenshell.util.element
import ifcopenshell.util.classification
from typing import Any

from ..models.ifc import SelectionAnalysis, SharedValue

def extract_material_layer_set(layer_set):
    if not layer_set:
        return None
    layers = getattr(layer_set, "MaterialLayers", []) or []
    layer_data = []
    for layer in layers:
        mat = getattr(layer, "Material", None)
        mat_name = getattr(mat, "Name", "Unnamed") if mat else "Unnamed"
        thickness = getattr(layer, "LayerThickness", None)
        layer_data.append({
            "name": mat_name,
            "thickness": thickness
        })
    return {
        "type": "layer_set",
        "name": getattr(layer_set, "MaterialSetName", None) or getattr(layer_set, "LayerSetName", None) or "Unnamed Layer Set",
        "layers": layer_data
    }

def extract_material_profile_set(profile_set):
    if not profile_set:
        return None
    profiles = getattr(profile_set, "MaterialProfiles", []) or []
    profile_data = []
    for profile in profiles:
        mat = getattr(profile, "Material", None)
        mat_name = getattr(mat, "Name", "Unnamed") if mat else "Unnamed"
        profile_data.append({
            "name": mat_name
        })
    return {
        "type": "profile_set",
        "name": getattr(profile_set, "Name", None) or "Unnamed Profile Set",
        "profiles": profile_data
    }

def extract_material_data(mat_info):
    if not mat_info:
        return None

    if isinstance(mat_info, (list, tuple)):
        sub_mats = []
        for m in mat_info:
            data = extract_material_data(m)
            if data:
                sub_mats.append(data)
        if not sub_mats:
            return None
        if len(sub_mats) == 1:
            return sub_mats[0]
        return {
            "type": "list",
            "materials": sub_mats
        }

    if not hasattr(mat_info, "is_a"):
        return None

    if mat_info.is_a("IfcMaterialLayerSetUsage"):
        layer_set = getattr(mat_info, "ForLayerSet", None)
        return extract_material_layer_set(layer_set)
    elif mat_info.is_a("IfcMaterialLayerSet"):
        return extract_material_layer_set(mat_info)
    elif mat_info.is_a("IfcMaterialProfileSetUsage"):
        profile_set = getattr(mat_info, "ForProfileSet", None)
        return extract_material_profile_set(profile_set)
    elif mat_info.is_a("IfcMaterialProfileSet"):
        return extract_material_profile_set(mat_info)
    elif mat_info.is_a("IfcMaterialList"):
        materials = getattr(mat_info, "Materials", []) or []
        sub_mats = [extract_material_data(m) for m in materials if m]
        return {
            "type": "list",
            "materials": [m for m in sub_mats if m]
        }
    elif mat_info.is_a("IfcMaterialConstituentSet"):
        constituents = getattr(mat_info, "MaterialConstituents", []) or []
        sub_mats = []
        for c in constituents:
            mat = getattr(c, "Material", None)
            if mat:
                sub_mats.append(extract_material_data(mat))
        return {
            "type": "list",
            "materials": [m for m in sub_mats if m]
        }
    elif mat_info.is_a("IfcMaterialConstituent"):
        mat = getattr(mat_info, "Material", None)
        if mat:
            return extract_material_data(mat)
        return {"type": "single", "name": getattr(mat_info, "Name", "Unnamed")}
    elif mat_info.is_a("IfcMaterialProfile"):
        mat = getattr(mat_info, "Material", None)
        if mat:
            return extract_material_data(mat)
        return {"type": "single", "name": getattr(mat_info, "Name", "Unnamed")}
    elif mat_info.is_a("IfcMaterial"):
        return {
            "type": "single",
            "name": getattr(mat_info, "Name", "Unnamed")
        }

    return {
        "type": "single",
        "name": getattr(mat_info, "Name", "Unnamed") or mat_info.is_a()
    }


def analyze_guids(model: ifcopenshell.file, guids: list[str]) -> SelectionAnalysis:
    import time
    if not guids:
        return SelectionAnalysis(common_attributes={}, common_psets={}, common_classifications={}, common_materials={})

    start_lookup = time.perf_counter()
    elements = [
        model.by_guid(g)
        for g in guids
        if getattr(model, "by_guid", None) and model.by_guid(g)
    ]
    # filter out Nones
    elements = [e for e in elements if e is not None]
    lookup_duration = (time.perf_counter() - start_lookup) * 1000
    print(f"[Perf] analyze_guids | by_guid resolution for {len(guids)} elements took {lookup_duration:.2f}ms")

    if not elements:
        return SelectionAnalysis(common_attributes={}, common_psets={}, common_classifications={}, common_materials={})

    # Intersect attributes (Restricted to Whitelist + Entity Type)
    common_attributes = {}
    
    # 1. Entity Type (is_a)
    types = [e.is_a() for e in elements]
    unique_types = sorted(list(set(types)))
    if len(unique_types) == 1:
        common_attributes["Entity"] = SharedValue(value=unique_types[0], is_mixed=False)

    # 2. Core Attributes (obtained dynamically from element info)
    all_attrs = set()
    if elements:
        try:
            all_attrs = set(elements[0].get_info().keys())
            for e in elements[1:]:
                all_attrs.intersection_update(e.get_info().keys())
        except Exception:
            all_attrs = {"Name", "ObjectType", "Description", "Tag"}

    for attr in all_attrs:
        if attr in ("id", "type", "GlobalId", "OwnerHistory"):
            continue
        vals = [getattr(e, attr, None) for e in elements]
        if all(v is None for v in vals):
            continue
        val1 = vals[0]
        unique_vals = list(set([str(v) if v is not None else "" for v in vals]))
        is_mixed = len(unique_vals) > 1

        if is_mixed:
            common_attributes[attr] = SharedValue(
                value="<Mixed>",
                is_mixed=True,
                other_values=unique_vals
            )
        else:
            common_attributes[attr] = SharedValue(value=val1, is_mixed=False)

    # 3. Spatial Containment (Storey)
    storeys_for_elements = []
    for e in elements:
        found_storey = False
        for rel in list(getattr(e, "ContainedInStructure", []) or []):
            if rel.is_a("IfcRelContainedInSpatialStructure") and rel.RelatingStructure.is_a("IfcBuildingStorey"):
                storeys_for_elements.append(getattr(rel.RelatingStructure, "Name", ""))
                found_storey = True
                break
        if not found_storey:
            storeys_for_elements.append(None)

    if storeys_for_elements and all(s is not None for s in storeys_for_elements):
        unique_storeys = list(set(storeys_for_elements))
        if len(unique_storeys) == 1:
            common_attributes["Storey"] = SharedValue(value=unique_storeys[0], is_mixed=False)
        else:
            common_attributes["Storey"] = SharedValue(value="<Mixed>", is_mixed=True, other_values=unique_storeys)

    # Intersect Psets
    start_psets = time.perf_counter()
    all_psets = [ifcopenshell.util.element.get_psets(e) for e in elements]
    psets_duration = (time.perf_counter() - start_psets) * 1000
    print(f"[Perf] analyze_guids | get_psets extraction for {len(elements)} elements took {psets_duration:.2f}ms")
    
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
            
            # Check if all elements in the selection actually have this property
            prop_vals = [psets[pset_name][prop] for psets in all_psets]
            val1 = prop_vals[0]
            # Safe unique values (handle unhashable types like dicts)
            try:
                unique_vals = list(set(prop_vals))
            except TypeError:
                unique_vals = []
                for v in prop_vals:
                    if v not in unique_vals:
                        unique_vals.append(v)
            
            # It's mixed if values differ OR if not all elements share this property
            is_mixed = len(prop_vals) != len(elements) or len(unique_vals) > 1

            if is_mixed:
                common_psets[pset_name][prop] = SharedValue(
                    value="<Mixed>", 
                    is_mixed=True,
                    other_values=unique_vals
                )
            else:
                common_psets[pset_name][prop] = SharedValue(value=val1, is_mixed=False)

    # Intersect Classifications
    all_classifications_data = []
    for e in elements:
        refs = ifcopenshell.util.classification.get_references(e)
        element_map = {}
        for ref in refs:
            system = ifcopenshell.util.classification.get_classification(ref)
            system_name = system.Name if system else "Unknown"
            code = getattr(ref, "Identification", getattr(ref, "ItemReference", None))
            element_map[system_name] = code
        all_classifications_data.append(element_map)

    common_systems = set(all_classifications_data[0].keys()) if all_classifications_data else set()
    for element_map in all_classifications_data[1:]:
        common_systems.intersection_update(element_map.keys())

    common_classifications = {}
    for system_name in common_systems:
        codes = [element_map[system_name] for element_map in all_classifications_data]
        unique_codes = list(set(codes))
        is_mixed = len(unique_codes) > 1

        if is_mixed:
            common_classifications[system_name] = SharedValue(
                value="<Mixed>",
                is_mixed=True,
                other_values=[str(c) for c in unique_codes]
            )
        else:
            common_classifications[system_name] = SharedValue(value=str(codes[0]), is_mixed=False)

    # Intersect Materials
    element_structures = []
    for e in elements:
        mat_info = ifcopenshell.util.element.get_material(e)
        extracted = extract_material_data(mat_info)
        element_structures.append(extracted)

    unique_structures = []
    for struct in element_structures:
        if struct is not None and struct not in unique_structures:
            unique_structures.append(struct)

    common_materials = {}

    if len(unique_structures) == 1:
        struct = unique_structures[0]
        # Resolve a name for the dictionary key
        if struct.get("type") == "single":
            name = struct.get("name", "Unnamed")
        else:
            name = struct.get("name") or (struct.get("materials", [{}])[0].get("name", "Unnamed") if struct.get("materials") else "Composite")
        common_materials[name] = SharedValue(
            value=name,
            is_mixed=False,
            structure=struct
        )
    elif len(unique_structures) > 1:
        names = []
        for struct in unique_structures:
            if struct.get("type") == "single":
                n = struct.get("name", "Unnamed")
            else:
                n = struct.get("name") or (struct.get("materials", [{}])[0].get("name", "Unnamed") if struct.get("materials") else "Composite")
            names.append(n)
        
        common_materials["Material"] = SharedValue(
            value="<Mixed>",
            is_mixed=True,
            other_values=names,
            structure=None
        )

    return SelectionAnalysis(
        common_attributes=common_attributes,
        common_psets=common_psets,
        common_classifications=common_classifications,
        common_materials=common_materials,
    )


def filter_by_property(
    model: ifcopenshell.file,
    guids: list[str],
    pset_name: str | None,
    prop_name: str,
    target_value: Any,
) -> list[str]:
    """Return subset of GUIDs where the specified property matches the target value."""
    # target_value might be coming from JSON, normalize it
    tv = str(target_value) if target_value is not None else ""

    matching_guids = []
    for guid in guids:
        try:
            element = model.by_guid(guid)
            if not element:
                continue

            current_val = None
            if pset_name:
                # Property Case
                psets = ifcopenshell.util.element.get_psets(element)
                if pset_name in psets and prop_name in psets[pset_name]:
                    current_val = psets[pset_name][prop_name]
            else:
                # Attribute Case
                info = element.get_info()
                if prop_name in info:
                    current_val = info[prop_name]

            # Compare as strings for maximum compatibility
            if str(current_val) == tv:
                matching_guids.append(guid)
        except Exception:
            continue

    return matching_guids

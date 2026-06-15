
import ifcopenshell
import ifcopenshell.util.element
import ifcopenshell.util.classification
from typing import Any

from ..models.ifc import SelectionAnalysis, SharedValue


def analyze_guids(model: ifcopenshell.file, guids: list[str]) -> SelectionAnalysis:
    if not guids:
        return SelectionAnalysis(common_attributes={}, common_psets={}, common_classifications={}, common_materials={})

    elements = [
        model.by_guid(g)
        for g in guids
        if getattr(model, "by_guid", None) and model.by_guid(g)
    ]
    # filter out Nones
    elements = [e for e in elements if e is not None]

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
    all_materials_data = []
    for e in elements:
        mat_info = ifcopenshell.util.element.get_material(e)
        # get_material can return a single material element, a list, or a material layer set etc.
        # We simplify to a set of names present on the element
        names = set()
        if mat_info:
            if isinstance(mat_info, (list, tuple)):
                for m in mat_info:
                    names.add(str(getattr(m, "Name", "Unnamed")))
            elif hasattr(mat_info, "is_a") and mat_info.is_a("IfcMaterialLayerSetUsage"):
                for layer in mat_info.ForLayerSet.MaterialLayers:
                    names.add(str(getattr(layer.Material, "Name", "Unnamed")))
            else:
                names.add(str(getattr(mat_info, "Name", "Unnamed")))
        all_materials_data.append(names)

    common_material_names = set(all_materials_data[0]) if all_materials_data else set()
    for names in all_materials_data[1:]:
        common_material_names.intersection_update(names)

    common_materials = {}
    for mat_name in common_material_names:
        common_materials[mat_name] = SharedValue(value=mat_name, is_mixed=False)

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

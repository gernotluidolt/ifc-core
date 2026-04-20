
import ifcopenshell
import ifcopenshell.util.element
import ifcopenshell.util.classification
from typing import Any

from ..models.ifc import SelectionAnalysis, SharedValue


def analyze_guids(model: ifcopenshell.file, guids: list[str]) -> SelectionAnalysis:
    if not guids:
        return SelectionAnalysis(common_attributes={}, common_psets={})

    elements = [
        model.by_guid(g)
        for g in guids
        if getattr(model, "by_guid", None) and model.by_guid(g)
    ]
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
        all_vals = [info[key] for info in infos]
        is_mixed = any(v != val1 for v in all_vals[1:])

        if is_mixed:
            common_attributes[key] = SharedValue(
                value="<Mixed>", 
                is_mixed=True, 
                other_values=list(set(all_vals))
            )
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
            
            # Check if all elements in the selection actually have this property
            prop_vals = [psets[pset_name][prop] for psets in all_psets]
            val1 = prop_vals[0]
            unique_vals = list(set(prop_vals))
            
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
            # In IfcOpenShell, identification is usually stored in Identification (IFC4) or ItemReference (IFC2x3)
            code = getattr(ref, "Identification", getattr(ref, "ItemReference", None))
            element_map[system_name] = code
        all_classifications_data.append(element_map)

    # Find system names present in ALL elements
    if not all_classifications_data:
        common_systems = set()
    else:
        common_systems = set(all_classifications_data[0].keys())
        for element_map in all_classifications_data[1:]:
            common_systems.intersection_update(element_map.keys())

    common_classifications = {}
    for system_name in common_systems:
        # Check if the code for this system is consistent
        codes = [element_map[system_name] for element_map in all_classifications_data]
        val1 = codes[0]
        unique_codes = list(set(codes))
        is_mixed = len(unique_codes) > 1

        if is_mixed:
            common_classifications[system_name] = SharedValue(
                value="<Mixed>",
                is_mixed=True,
                other_values=[str(c) for c in unique_codes]
            )
        else:
            common_classifications[system_name] = SharedValue(value=str(val1), is_mixed=False)

    return SelectionAnalysis(
        common_attributes=common_attributes,
        common_psets=common_psets,
        common_classifications=common_classifications,
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

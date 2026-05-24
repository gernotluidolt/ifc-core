
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

    # Intersect attributes (Restricted to Whitelist + Entity Type)
    common_attributes = {}
    
    # 1. Entity Type (is_a)
    types = [e.is_a() for e in elements]
    unique_types = sorted(list(set(types)))
    if len(unique_types) == 1:
        common_attributes["Entity"] = SharedValue(value=unique_types[0], is_mixed=False)

    # 2. Whitelisted Core Attributes
    whitelist = ["Name", "ObjectType", "Tag", "Description", "GlobalId"]
    for attr in whitelist:
        # Only include if EVERY element possesses this attribute
        if not all(hasattr(e, attr) for e in elements):
            continue
            
        vals = [getattr(e, attr, None) for e in elements]
        val1 = vals[0]
        unique_vals = list(set([str(v) if v is not None else "" for v in vals]))
        is_mixed = len(unique_vals) > 1

        if not is_mixed:
            common_attributes[attr] = SharedValue(value=val1, is_mixed=False)

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
        try:
            unique_codes = list(set(codes))
        except TypeError:
            unique_codes = []
            for c in codes:
                if c not in unique_codes:
                    unique_codes.append(c)
        is_mixed = len(unique_codes) > 1

        if is_mixed:
            common_classifications[system_name] = SharedValue(
                value="<Mixed>",
                is_mixed=True,
                other_values=[str(c) for c in unique_codes]
            )
        else:
            common_classifications[system_name] = SharedValue(value=str(val1), is_mixed=False)

    # Intersect PartOf
    all_partof_data = []
    for e in elements:
        parents = []
        for rel in getattr(e, "ContainedInStructure", []):
            if rel.RelatingStructure:
                parents.append(rel.RelatingStructure)
        for rel in getattr(e, "Decomposes", []):
            if rel.RelatingObject:
                parents.append(rel.RelatingObject)
        for rel in getattr(e, "HasAssignments", []):
            if rel.is_a("IfcRelAssignsToGroup") and rel.RelatingGroup:
                parents.append(rel.RelatingGroup)
                
        element_map = {}
        for p in parents:
            element_map[p.is_a()] = getattr(p, "Name", p.GlobalId)
        all_partof_data.append(element_map)

    if not all_partof_data:
        common_parents = set()
    else:
        common_parents = set(all_partof_data[0].keys())
        for element_map in all_partof_data[1:]:
            common_parents.intersection_update(element_map.keys())

    common_partof = {}
    for parent_type in common_parents:
        names = [element_map[parent_type] for element_map in all_partof_data]
        val1 = names[0]
        try:
            unique_names = list(set(names))
        except TypeError:
            unique_names = []
            for n in names:
                if n not in unique_names:
                    unique_names.append(n)
        is_mixed = len(unique_names) > 1
        common_partof[parent_type] = SharedValue(
            value="<Mixed>" if is_mixed else str(val1),
            is_mixed=is_mixed,
            other_values=[str(n) for n in unique_names] if is_mixed else []
        )

    # Intersect Materials
    all_materials_data = []
    for e in elements:
        mat = ifcopenshell.util.element.get_material(e)
        if mat:
            if mat.is_a("IfcMaterial"):
                all_materials_data.append(mat.Name)
            elif mat.is_a("IfcMaterialList"):
                all_materials_data.append(mat.Materials[0].Name if mat.Materials else "")
            elif mat.is_a("IfcMaterialLayerSetUsage"):
                try:
                    all_materials_data.append(mat.ForLayerSet.MaterialLayers[0].Material.Name)
                except Exception:
                    all_materials_data.append("")
            elif mat.is_a("IfcMaterialProfileSetUsage"):
                try:
                    all_materials_data.append(mat.ForProfileSet.MaterialProfiles[0].Material.Name)
                except Exception:
                    all_materials_data.append("")
            else:
                all_materials_data.append(getattr(mat, "Name", ""))
        else:
            all_materials_data.append("")

    unique_mats = list(set([m for m in all_materials_data if m]))
    is_mixed_mat = len(all_materials_data) > 1 and len(unique_mats) > 1
    # also it is mixed if some have material and some don't
    has_empty = any(not m for m in all_materials_data)
    is_mixed_mat = is_mixed_mat or (has_empty and len(unique_mats) > 0)
    
    common_materials = {}
    if unique_mats:
        common_materials["Material"] = SharedValue(
            value="<Mixed>" if is_mixed_mat else unique_mats[0],
            is_mixed=is_mixed_mat,
            other_values=unique_mats if is_mixed_mat else []
        )

    return SelectionAnalysis(
        common_attributes=common_attributes,
        common_psets=common_psets,
        common_classifications=common_classifications,
        common_partof=common_partof,
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

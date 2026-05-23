from typing import Any

import ifcopenshell.util.element

from ..models.ids import IdsRequirement, IdsSpecification
from ..models.ifc import MappingState, MappingStatus


def _get_property_value(element, pset_name: str, prop_name: str) -> Any:
    psets = ifcopenshell.util.element.get_psets(element)
    
    # Case-insensitive Pset lookup
    target_pset_key = pset_name.lower()
    found_pset = None
    for k in psets.keys():
        if k.lower() == target_pset_key:
            found_pset = psets[k]
            break
    
    if found_pset is not None:
        # Case-insensitive Property lookup
        target_prop_key = prop_name.lower()
        for k in found_pset.keys():
            if k.lower() == target_prop_key:
                return found_pset[k]
                
    return None


def _get_attribute_value(element, attr_name: str) -> Any:
    # Some IFCOpenShell versions capitalize attributes
    # But usually hasattr or getattr works if case matches schema
    if hasattr(element, attr_name):
        return getattr(element, attr_name)
    # Alternatively get_info()
    info = element.get_info()
    if attr_name in info:
        return info[attr_name]
    return None

def _get_material_value(element) -> Any:
    for rel in getattr(element, "HasAssociations", []):
        if rel.is_a("IfcRelAssociatesMaterial"):
            mat_select = rel.RelatingMaterial
            if not mat_select:
                continue
            if mat_select.is_a("IfcMaterial"):
                return mat_select.Name
            elif mat_select.is_a("IfcMaterialLayerSetUsage"):
                layers = mat_select.ForLayerSet.MaterialLayers
                if layers and layers[0].Material:
                    return layers[0].Material.Name
            elif mat_select.is_a("IfcMaterialLayerSet"):
                layers = mat_select.MaterialLayers
                if layers and layers[0].Material:
                    return layers[0].Material.Name
            elif mat_select.is_a("IfcMaterialList"):
                materials = mat_select.Materials
                if materials:
                    return materials[0].Name
    return None

def _get_classification_value(element, system_name: str) -> Any:
    for rel in getattr(element, "HasAssociations", []):
        if rel.is_a("IfcRelAssociatesClassification"):
            cls_ref = rel.RelatingClassification
            if cls_ref.is_a("IfcClassificationReference"):
                ref_system = ""
                if getattr(cls_ref, "ReferencedSource", None):
                    ref_system = getattr(cls_ref.ReferencedSource, "Name", "")
                
                # If a specific system name is requested, ensure it matches
                if not system_name or (system_name.lower() in ref_system.lower() or ref_system.lower() in system_name.lower()):
                    return getattr(cls_ref, "Identification", getattr(cls_ref, "ItemReference", None))
    return None

def _check_part_of(element, req: IdsRequirement) -> bool:
    target_entity = req.name  # e.g. "IFCSPACE"
    if not target_entity:
        return False
    
    target_relation = req.value  # e.g. "IFCRELCONTAINEDINSPATIALSTRUCTURE", optional

    def get_parents(el):
        parents = []
        # Spatial containment
        for rel in getattr(el, "ContainedInStructure", []):
            if not target_relation or target_relation.upper() == "IFCRELCONTAINEDINSPATIALSTRUCTURE":
                parents.append(rel.RelatingStructure)
        
        # Aggregation
        for rel in getattr(el, "Decomposes", []):
            if not target_relation or target_relation.upper() == "IFCRELAGGREGATES":
                parents.append(rel.RelatingObject)

        # Nesting
        for rel in getattr(el, "Nests", []):
            if not target_relation or target_relation.upper() == "IFCRELNESTS":
                parents.append(rel.RelatingObject)
        
        # Assignment to group
        for rel in getattr(el, "HasAssignments", []):
            if rel.is_a("IfcRelAssignsToGroup"):
                if not target_relation or target_relation.upper() == "IFCRELASSIGNSTOGROUP":
                    parents.append(rel.RelatingGroup)

        # Voids/Fills
        for rel in getattr(el, "VoidsElements", []):
            if not target_relation or target_relation.upper() == "IFCRELVOIDSELEMENT":
                parents.append(rel.RelatingBuildingElement)
        
        for rel in getattr(el, "FillsVoids", []):
            if not target_relation or target_relation.upper() == "IFCRELFILLSELEMENT":
                parents.append(rel.RelatingOpeningElement)
                
        return parents

    visited = set()
    queue = get_parents(element)
    
    while queue:
        current = queue.pop(0)
        if current.GlobalId in visited:
            continue
        visited.add(current.GlobalId)
        
        if current.is_a(target_entity):
            return True
        
        queue.extend(get_parents(current))
        
    return False



def _check_value_against_options(value: Any, req: IdsRequirement) -> bool:
    if value is None:
        return False

    val_str = str(value)

    # 1. Direct explicit options
    if req.options and val_str not in req.options:
        return False

    # 2. Extract options dumped into value string by ifctester (e.g. "{'enumeration': ['...']}")
    if req.value and isinstance(req.value, str):
        if "'enumeration':" in req.value:
            import re
            match = re.search(r"'enumeration':\s*\[(.*?)\]", req.value)
            if match:
                # 'A', 'B' -> split and strip
                raw_opts = match.group(1).split(",")
                parsed_opts = [opt.strip().strip("'").strip('"') for opt in raw_opts]
                if val_str not in parsed_opts:
                    return False
                return True # Passed enumeration! No need to strict match the dump string.

    # 3. Numeric bounds
    try:
        val_float = float(value)
        if req.min_inclusive is not None and val_float < req.min_inclusive:
            return False
        if req.max_inclusive is not None and val_float > req.max_inclusive:
            return False
    except ValueError:
        pass

    # 4. Strict exact match for singular literal string requirements
    if req.value and not "'enumeration':" in str(req.value):
        if val_str != str(req.value):
            return False

    return True


def _is_applicable(element, applicability: list[IdsRequirement]) -> bool:
    if not applicability:
        return True  # Applies to all if empty?

    for req in applicability:
        req_type = req.type.lower()

        if req_type == "entity":
            if not getattr(req, "name", None):
                continue
            if not element.is_a(req.name):
                return False

        elif req_type == "property":
            val = _get_property_value(element, req.property_set, req.name)
            if not _check_value_against_options(val, req):
                return False

        elif req_type == "attribute":
            val = _get_attribute_value(element, req.name)
            if not _check_value_against_options(val, req):
                return False

        elif req_type == "material":
            val = _get_material_value(element)
            if not _check_value_against_options(val, req):
                return False
                
        elif req_type == "classification":
            val = _get_classification_value(element, req.name)
            if not _check_value_against_options(val, req):
                return False
                
        elif req_type == "partof":
            if not _check_part_of(element, req):
                return False

    return True


def check_mapping_status(element, spec: IdsSpecification) -> MappingStatus:
    guid = getattr(element, "GlobalId", "Unknown")

    # 1. Check Applicability
    if not _is_applicable(element, spec.applicability):
        return MappingStatus(
            element_guid=guid,
            spec_name=spec.name,
            state=MappingState.UNMAPPED,
            missing_requirements=[],
            invalid_requirements=[],
        )

    missing = []
    invalid = []

    # 2. Check Requirements
    for req in spec.requirements:
        req_type = req.type.lower()
        val = None

        if req_type == "entity":
            if getattr(req, "name", None) and not element.is_a(req.name):
                invalid.append(req)
            continue
            
        elif req_type == "property":
            val = _get_property_value(element, req.property_set, req.name)
        elif req_type == "attribute":
            val = _get_attribute_value(element, req.name)
        elif req_type == "material":
            val = _get_material_value(element)
        elif req_type == "classification":
            val = _get_classification_value(element, req.name)
        elif req_type == "partof":
            if not _check_part_of(element, req):
                missing.append(req)
            continue

        if val is None:
            missing.append(req)
        elif not _check_value_against_options(val, req):
            invalid.append(req)

    if missing:
        state = MappingState.INCOMPLETE
    elif invalid:
        state = MappingState.INVALID
    else:
        state = MappingState.COMPLIANT

    return MappingStatus(
        element_guid=guid,
        spec_name=spec.name,
        state=state,
        missing_requirements=missing,
        invalid_requirements=invalid,
    )

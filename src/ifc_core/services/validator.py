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

        if req_type == "property":
            val = _get_property_value(element, req.property_set, req.name)
        elif req_type == "attribute":
            val = _get_attribute_value(element, req.name)
        # Note: Material and Classification handling can be added here

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

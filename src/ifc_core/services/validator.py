from typing import Any
import re

import ifcopenshell.util.element

from ..models.ids import IdsRequirement, IdsSpecification
from ..models.ifc import MappingState, MappingStatus
from .inspector import extract_material_data


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


def _get_requirement_values(element, req: IdsRequirement) -> list[Any]:
    vals = []
    req_type = req.type.lower()
    try:
        if req_type == "attribute":
            val = _get_attribute_value(element, req.name)
            if val is not None:
                vals.append(val)
        elif req_type == "property":
            val = _get_property_value(element, req.property_set, req.name)
            if val is not None:
                vals.append(val)
        elif req_type == "partof": # Storey
            for rel in list(getattr(element, "ContainedInStructure", []) or []):
                if rel.is_a("IfcRelContainedInSpatialStructure") and rel.RelatingStructure:
                    vals.append(getattr(rel.RelatingStructure, "Name", ""))
                    break
        elif req_type == "material":
            mat_info = ifcopenshell.util.element.get_material(element)
            extracted = extract_material_data(mat_info)
            if extracted:
                if extracted.get("type") == "single":
                    vals.append(extracted.get("name"))
                elif extracted.get("type") == "list":
                    for sub in extracted.get("materials", []):
                        vals.append(sub.get("name"))
                elif extracted.get("type") == "layer_set":
                    for layer in extracted.get("layers", []):
                        vals.append(layer.get("name"))
                elif extracted.get("type") == "profile_set":
                    for prof in extracted.get("profiles", []):
                        vals.append(prof.get("name"))
        elif req_type == "classification":
            import ifcopenshell.util.classification
            try:
                refs = ifcopenshell.util.classification.get_references(element)
                for ref in refs:
                    try:
                        system = ifcopenshell.util.classification.get_classification(ref)
                        system_name = getattr(system, "Name", "") if system else ""
                        if not system_name and ref.is_a("IfcClassification"):
                            system_name = getattr(ref, "Name", "")
                        
                        if system_name.lower() == (req.name or "").lower():
                            code = getattr(ref, "Identification", getattr(ref, "ItemReference", None))
                            name = getattr(ref, "Name", None)
                            if code is not None: vals.append(code)
                            if name is not None: vals.append(name)
                    except Exception:
                        continue
            except Exception:
                pass
    except Exception:
        pass
    return vals


def _is_applicable(element, applicability: list[IdsRequirement]) -> bool:
    if not applicability:
        return True

    for req in applicability:
        req_type = req.type.lower()

        if req_type == "entity":
            if not getattr(req, "name", None):
                continue
            if not element.is_a(req.name):
                return False
        else:
            vals = _get_requirement_values(element, req)
            valid_vals = [v for v in vals if v is not None and str(v).strip() != "" and str(v) != "<Mixed>"]
            if not valid_vals:
                return False
            if not any(_check_value_against_options(v, req) for v in valid_vals):
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
        vals = _get_requirement_values(element, req)
        valid_vals = [v for v in vals if v is not None and str(v).strip() != "" and str(v) != "<Mixed>"]

        if not valid_vals:
            if getattr(req, "cardinality", None) != "optional":
                missing.append(req)
        else:
            if not any(_check_value_against_options(v, req) for v in valid_vals):
                if getattr(req, "cardinality", None) != "optional":
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

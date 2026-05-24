from pathlib import Path

import ifctester

from ..models.ids import IdsRequirement, IdsSpecification


def _map_facet_to_requirement(facet) -> IdsRequirement:
    if hasattr(facet, "is_a") and callable(facet.is_a):
        req_type = str(facet.is_a()).lower()
    else:
        req_type = facet.__class__.__name__.lower()

    raw_name = getattr(facet, "name", None)
    raw_base_name = getattr(facet, "baseName", None)
    req_name = raw_name if isinstance(raw_name, str) and raw_name else None
    if req_name is None and isinstance(raw_base_name, str) and raw_base_name:
        req_name = raw_base_name

    raw_property_set = getattr(facet, "property_set", None)
    raw_property_set_alt = getattr(facet, "propertySet", None)
    req_property_set = (
        raw_property_set
        if isinstance(raw_property_set, str) and raw_property_set
        else None
    )
    if (
        req_property_set is None
        and isinstance(raw_property_set_alt, str)
        and raw_property_set_alt
    ):
        req_property_set = raw_property_set_alt
    options = []
    min_val = None
    max_val = None
    pattern = None
    data_type = None
    raw_value = getattr(facet, "value", None)

    # ifctester may represent restrictions either in "restriction" or in a dict-like "value"
    restriction = getattr(facet, "restriction", None)
    if restriction is None and isinstance(raw_value, dict):
        restriction = raw_value

    # For entity facets, class names are commonly stored in the "name" field.
    if raw_value is None and req_type == "entity":
        raw_value = req_name
    
    # Classification/Material Support: extract system name/identifier
    raw_system = getattr(facet, "system", None)
    if not req_name and isinstance(raw_system, str) and raw_system:
        req_name = raw_system

    # PartOf Support: extract target entity and relation
    if req_type == "partof":
        raw_entity = getattr(facet, "entity", None)
        if raw_entity:
            if hasattr(raw_entity, "name"):
                req_name = str(getattr(raw_entity.name, "value", raw_entity.name) if hasattr(raw_entity.name, "value") else raw_entity.name)
            else:
                req_name = str(raw_entity)
        
        raw_relation = getattr(facet, "relation", None)
        if raw_relation:
            if hasattr(raw_relation, "name"):
                raw_value = str(getattr(raw_relation.name, "value", raw_relation.name) if hasattr(raw_relation.name, "value") else raw_relation.name)
            else:
                raw_value = str(raw_relation)

    # Check for restrictions (Enumerations/Ranges/Patterns)
    has_restriction_data = False
    res_opts = getattr(raw_value, "options", None) if not isinstance(raw_value, dict) else raw_value
    if isinstance(res_opts, dict):
        if any(k in res_opts for k in ("enumeration", "pattern", "pattern_value", "minInclusive", "maxInclusive")):
            has_restriction_data = True
            
    if restriction is None and has_restriction_data:
        restriction = raw_value

    if restriction:
        res = restriction
        # Get options dict either from dict itself or from Restriction object
        opts = res if isinstance(res, dict) else getattr(res, "options", {})
        
        if isinstance(opts, dict):
            if "enumeration" in opts:
                options = [str(v) for v in opts["enumeration"]]
            if "minInclusive" in opts and opts["minInclusive"] is not None:
                min_val = float(opts["minInclusive"])
            if "maxInclusive" in opts and opts["maxInclusive"] is not None:
                max_val = float(opts["maxInclusive"])
            if "pattern" in opts and opts["pattern"]:
                pattern = str(opts["pattern"])
            elif "pattern_value" in opts and opts["pattern_value"]:
                pattern = str(opts["pattern_value"])
                
        # Extract base type from ifctester object
        if hasattr(res, "base") and res.base:
            data_type = str(res.base).replace("xs:", "")
        elif hasattr(res, "baseName") and res.baseName:
            data_type = str(res.baseName).replace("xs:", "")

            # Handle Regex Pattern
            if hasattr(res, "pattern") and res.pattern is not None:
                pattern = str(res.pattern)
            elif hasattr(res, "pattern_value") and res.pattern_value is not None:
                pattern = str(res.pattern_value)

    # Some facets have dataType directly on the facet itself (like property facets)
    if not data_type:
        dt = getattr(facet, "dataType", getattr(facet, "data_type", None))
        if dt:
            data_type = str(dt).replace("xs:", "")

    # Final Value resolution
    final_value = None
    if raw_value is not None and not isinstance(raw_value, dict) and restriction is None:
        final_value = str(raw_value)
    
    # Smart Fallback: if we have exactly one option, we can use it as a concrete value
    if final_value is None and len(options) == 1:
        final_value = options[0]

    return IdsRequirement(
        type=req_type,
        name=req_name,
        value=final_value,
        property_set=req_property_set,
        instructions=getattr(facet, "instructions", None),
        options=options,
        data_type=data_type,
        min_inclusive=min_val,
        max_inclusive=max_val,
        pattern=pattern,
    )


def parse_ids_file(path: Path) -> list[IdsSpecification]:
    """Opens an IDS file and returns a list of high-level Spec objects."""
    ids_data = ifctester.ids.open(str(path))
    parsed_specs = []

    for spec in ids_data.specifications:
        # Extract Applicability (Filters)
        applicability = [_map_facet_to_requirement(f) for f in spec.applicability]

        # Extract Requirements (Actual Rules)
        requirements = [_map_facet_to_requirement(r) for r in spec.requirements]

        parsed_specs.append(
            IdsSpecification(
                name=spec.name,
                identifier=getattr(spec, "identifier", None),
                description=getattr(spec, "description", None),
                instructions=getattr(spec, "instructions", None),
                min_occurs=getattr(spec, "min_occurs", None),
                max_occurs=getattr(spec, "max_occurs", None),
                applicability=applicability,
                requirements=requirements,
            )
        )

    return parsed_specs

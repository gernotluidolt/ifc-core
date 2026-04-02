import ifctester
from pathlib import Path
from typing import List
from ..models.ids import IdsSpecification, IdsRequirement


def _map_facet_to_requirement(facet) -> IdsRequirement:
    if hasattr(facet, "is_a") and callable(facet.is_a):
        req_type = str(facet.is_a()).lower()
    else:
        req_type = facet.__class__.__name__.lower()

    req_name = getattr(facet, "name", None) or getattr(facet, "baseName", None)
    req_property_set = getattr(facet, "property_set", None) or getattr(facet, "propertySet", None)
    options = []
    min_val = None
    max_val = None
    raw_value = getattr(facet, "value", None)

    # ifctester may represent restrictions either in "restriction" or in a dict-like "value"
    restriction = getattr(facet, "restriction", None)
    if restriction is None and isinstance(raw_value, dict):
        restriction = raw_value

    # For entity facets, class names are commonly stored in the "name" field.
    if raw_value is None and req_type == "entity":
        raw_value = req_name

    # Check for restrictions (Enumerations/Ranges)
    if restriction:
        res = restriction

        # Handle Enumerations (List of choices)
        if isinstance(res, dict):
            if res.get("enumeration"):
                options = [str(v) for v in res["enumeration"]]
            if res.get("minInclusive") is not None:
                min_val = float(res["minInclusive"])
            if res.get("maxInclusive") is not None:
                max_val = float(res["maxInclusive"])
        else:
            if hasattr(res, "enumeration") and res.enumeration:
                options = [str(v) for v in res.enumeration]

            # Handle Ranges
            if hasattr(res, "minInclusive") and res.minInclusive is not None:
                min_val = float(res.minInclusive)
            if hasattr(res, "maxInclusive") and res.maxInclusive is not None:
                max_val = float(res.maxInclusive)

    return IdsRequirement(
        type=req_type,
        name=req_name,
        value=str(raw_value) if raw_value is not None and not isinstance(raw_value, dict) else None,
        property_set=req_property_set,
        instructions=getattr(facet, "instructions", None),
        options=options,
        min_inclusive=min_val,
        max_inclusive=max_val,
    )


def parse_ids_file(path: Path) -> List[IdsSpecification]:
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

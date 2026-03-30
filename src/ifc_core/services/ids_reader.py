import ifctester
from pathlib import Path
from typing import List
from ..models.ids import IdsSpecification, IdsRequirement


def _map_facet_to_requirement(facet) -> IdsRequirement:
    req_type = facet.is_a()
    options = []
    min_val = None
    max_val = None

    # Check for restrictions (Enumerations/Ranges)
    if hasattr(facet, "restriction") and facet.restriction:
        res = facet.restriction

        # Handle Enumerations (List of choices)
        if hasattr(res, "enumeration") and res.enumeration:
            options = [str(v) for v in res.enumeration]

        # Handle Ranges
        if hasattr(res, "minInclusive"):
            min_val = float(res.minInclusive)
        if hasattr(res, "maxInclusive"):
            max_val = float(res.maxInclusive)

        return IdsRequirement(
            type=req_type,
            name=getattr(facet, "name", None),
            value=str(facet.value) if hasattr(facet, "value") and facet.value else None,
            property_set=getattr(facet, "property_set", None),
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
                identifier=spec.identifier,
                description=spec.description,
                instructions=spec.instructions,
                min_occurs=spec.min_occurs,
                max_occurs=spec.max_occurs,
                applicability=applicability,
                requirements=requirements,
            )
        )

    return parsed_specs

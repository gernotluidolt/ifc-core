import ifctester
from pathlib import Path
from typing import List
from ..models.ids import IdsSpecification, IdsRequirement


def _map_facet_to_requirement(facet) -> IdsRequirement:
    """Maps an internal ifctester facet to our clean Pydantic model."""
    req_type = facet.is_a()  # Returns 'Property', 'Attribute', etc.

    return IdsRequirement(
        type=req_type,
        name=getattr(facet, "name", None),
        value=str(facet.value) if hasattr(facet, "value") else None,
        property_set=getattr(facet, "property_set", None),
        instructions=getattr(facet, "instructions", None),
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

from pathlib import Path

import pytest

from ifc_core.services.ids_reader import parse_ids_file

IDS_FIXTURES = sorted(path for path in Path("tests/data").glob("*.ids"))


@pytest.mark.parametrize("ids_path", IDS_FIXTURES, ids=lambda path: path.name)
def test_parse_ids_file_with_real_ids(ids_path):
    specs = parse_ids_file(ids_path)

    assert len(specs) > 0

    first_spec = specs[0]
    assert first_spec.name
    assert first_spec.applicability
    assert first_spec.requirements

    first_applicability = first_spec.applicability[0]
    assert first_applicability.type
    if first_applicability.type != "entity":
        assert (
            first_applicability.name
            or first_applicability.value
            or first_applicability.property_set
        )

    first_requirement = first_spec.requirements[0]
    assert first_requirement.type
    if first_requirement.type != "entity":
        assert (
            first_requirement.name
            or first_requirement.value
            or first_requirement.property_set
        )

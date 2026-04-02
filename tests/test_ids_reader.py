from ifc_core.services.ids_reader import parse_ids_file


def test_parse_ids_file_with_real_ids(real_ids_path):
    specs = parse_ids_file(real_ids_path)

    assert len(specs) > 0

    first_spec = specs[0]
    assert first_spec.name
    assert first_spec.applicability
    assert first_spec.requirements

    first_applicability = first_spec.applicability[0]
    assert first_applicability.type
    assert first_applicability.name or first_applicability.value

    first_requirement = first_spec.requirements[0]
    assert first_requirement.type
    assert first_requirement.name or first_requirement.value

import ifcopenshell.api

from ifc_core.models.ids import IdsRequirement, IdsSpecification
from ifc_core.models.ifc import MappingState
from ifc_core.services import validator
from ifc_core.services.validator import check_mapping_status


def test_check_mapping_status_unmapped_when_applicability_fails(mock_ifc_store):
    wall = mock_ifc_store._model.by_type("IfcWall")[0]
    spec = IdsSpecification(
        name="DoorOnly",
        applicability=[IdsRequirement(type="entity", name="IfcDoor")],
        requirements=[],
    )

    status = check_mapping_status(wall, spec)
    assert status.state == MappingState.UNMAPPED
    assert status.missing_requirements == []
    assert status.invalid_requirements == []


def test_check_mapping_status_incomplete_when_property_missing(mock_ifc_store):
    wall = mock_ifc_store._model.by_type("IfcWall")[0]
    spec = IdsSpecification(
        name="RequiresWallPset",
        applicability=[IdsRequirement(type="entity", name="IfcWall")],
        requirements=[
            IdsRequirement(
                type="property",
                name="DefinitelyMissing",
                property_set="Pset_WallCommon",
                value="True",
            )
        ],
    )

    status = check_mapping_status(wall, spec)
    assert status.state == MappingState.INCOMPLETE
    assert len(status.missing_requirements) == 1
    assert status.invalid_requirements == []


def test_check_mapping_status_invalid_when_property_outside_restrictions(
    mock_ifc_store,
):
    wall = mock_ifc_store._model.by_type("IfcWall")[0]
    pset = ifcopenshell.api.run(
        "pset.add_pset", mock_ifc_store._model, product=wall, name="Pset_WallCommon"
    )
    ifcopenshell.api.run(
        "pset.edit_pset",
        mock_ifc_store._model,
        pset=pset,
        properties={"LoadBearing": False},
    )

    spec = IdsSpecification(
        name="StrictLoadBearing",
        applicability=[IdsRequirement(type="entity", name="IfcWall")],
        requirements=[
            IdsRequirement(
                type="property",
                name="LoadBearing",
                property_set="Pset_WallCommon",
                options=["True"],
            )
        ],
    )

    status = check_mapping_status(wall, spec)
    assert status.state == MappingState.INVALID
    assert status.missing_requirements == []
    assert len(status.invalid_requirements) == 1


def test_check_mapping_status_compliant_for_attribute_requirement(mock_ifc_store):
    wall = mock_ifc_store._model.by_type("IfcWall")[0]
    spec = IdsSpecification(
        name="WallNameMatches",
        applicability=[IdsRequirement(type="entity", name="IfcWall")],
        requirements=[
            IdsRequirement(
                type="attribute",
                name="Name",
                value=wall.Name,
            )
        ],
    )

    status = check_mapping_status(wall, spec)
    assert status.state == MappingState.COMPLIANT
    assert status.missing_requirements == []
    assert status.invalid_requirements == []


def test_check_value_against_options_and_ranges():
    req = IdsRequirement(
        type="attribute", options=["5"], min_inclusive=2, max_inclusive=10
    )
    assert validator._check_value_against_options(5, req)

    assert not validator._check_value_against_options(None, req)
    assert not validator._check_value_against_options(11, req)
    assert not validator._check_value_against_options(1, req)

    req_with_exact = IdsRequirement(type="attribute", value="Target")
    assert validator._check_value_against_options("Target", req_with_exact)
    assert not validator._check_value_against_options("Other", req_with_exact)

    req_non_numeric = IdsRequirement(
        type="attribute", min_inclusive=2, max_inclusive=10
    )
    assert validator._check_value_against_options("non-numeric", req_non_numeric)


def test_get_attribute_value_reads_real_attribute(real_ifc_store):
    wall = real_ifc_store._model.by_type("IfcWall")[0]
    assert validator._get_attribute_value(wall, "Name") == wall.Name


def test_get_attribute_value_returns_none_for_missing_real_attribute(real_ifc_store):
    wall = real_ifc_store._model.by_type("IfcWall")[0]
    assert validator._get_attribute_value(wall, "MissingAttr") is None


def test_is_applicable_true_for_real_wall_and_attribute_checks(real_ifc_store):
    wall = real_ifc_store._model.by_type("IfcWall")[0]
    applicability = [
        IdsRequirement(type="entity", name="IfcWall"),
        IdsRequirement(type="attribute", name="Name", value=wall.Name),
    ]

    assert validator._is_applicable(wall, applicability)


def test_is_applicable_true_when_empty_requirements(real_ifc_store):
    wall = real_ifc_store._model.by_type("IfcWall")[0]
    assert validator._is_applicable(wall, [])


def test_is_applicable_false_for_property_and_attribute_mismatch(mock_ifc_store):
    wall = mock_ifc_store._model.by_type("IfcWall")[0]

    pset = ifcopenshell.api.run(
        "pset.add_pset", mock_ifc_store._model, product=wall, name="Pset_WallCommon"
    )
    ifcopenshell.api.run(
        "pset.edit_pset",
        mock_ifc_store._model,
        pset=pset,
        properties={"LoadBearing": False},
    )

    property_mismatch = [
        IdsRequirement(
            type="property",
            name="LoadBearing",
            property_set="Pset_WallCommon",
            value="True",
        )
    ]
    attribute_mismatch = [
        IdsRequirement(type="attribute", name="Name", value=f"{wall.Name} (unexpected)")
    ]

    assert not validator._is_applicable(wall, property_mismatch)
    assert not validator._is_applicable(wall, attribute_mismatch)


def test_check_value_against_options_range_failures_without_options_gate():
    min_req = IdsRequirement(type="attribute", min_inclusive=2)
    max_req = IdsRequirement(type="attribute", max_inclusive=10)

    assert not validator._check_value_against_options(1, min_req)
    assert not validator._check_value_against_options(11, max_req)


def test_check_mapping_status_compliant_when_optional_property_missing(mock_ifc_store):
    wall = mock_ifc_store._model.by_type("IfcWall")[0]
    spec = IdsSpecification(
        name="OptionalMissing",
        applicability=[IdsRequirement(type="entity", name="IfcWall")],
        requirements=[
            IdsRequirement(
                type="property",
                name="DefinitelyMissing",
                property_set="Pset_WallCommon",
                value="True",
                cardinality="optional",
            )
        ],
    )

    status = check_mapping_status(wall, spec)
    assert status.state == MappingState.COMPLIANT
    assert status.missing_requirements == []
    assert status.invalid_requirements == []


def test_check_mapping_status_compliant_when_optional_property_present_and_valid(mock_ifc_store):
    wall = mock_ifc_store._model.by_type("IfcWall")[0]
    pset = ifcopenshell.api.run(
        "pset.add_pset", mock_ifc_store._model, product=wall, name="Pset_WallCommon"
    )
    ifcopenshell.api.run(
        "pset.edit_pset",
        mock_ifc_store._model,
        pset=pset,
        properties={"LoadBearing": True},
    )

    spec = IdsSpecification(
        name="OptionalValid",
        applicability=[IdsRequirement(type="entity", name="IfcWall")],
        requirements=[
            IdsRequirement(
                type="property",
                name="LoadBearing",
                property_set="Pset_WallCommon",
                value="True",
                cardinality="optional",
            )
        ],
    )

    status = check_mapping_status(wall, spec)
    assert status.state == MappingState.COMPLIANT
    assert status.missing_requirements == []
    assert status.invalid_requirements == []


def test_check_mapping_status_compliant_when_optional_property_present_and_invalid(mock_ifc_store):
    wall = mock_ifc_store._model.by_type("IfcWall")[0]
    pset = ifcopenshell.api.run(
        "pset.add_pset", mock_ifc_store._model, product=wall, name="Pset_WallCommon"
    )
    ifcopenshell.api.run(
        "pset.edit_pset",
        mock_ifc_store._model,
        pset=pset,
        properties={"LoadBearing": False},
    )

    spec = IdsSpecification(
        name="OptionalInvalidButIgnored",
        applicability=[IdsRequirement(type="entity", name="IfcWall")],
        requirements=[
            IdsRequirement(
                type="property",
                name="LoadBearing",
                property_set="Pset_WallCommon",
                value="True",
                cardinality="optional",
            )
        ],
    )

    status = check_mapping_status(wall, spec)
    assert status.state == MappingState.COMPLIANT
    assert status.missing_requirements == []
    assert status.invalid_requirements == []

"""FHIR shape tests for Practitioner / PractitionerRole / Location / facility Org."""

from __future__ import annotations

import pytest
from fhir.resources.R4B.location import Location as _Location
from fhir.resources.R4B.practitioner import Practitioner as _Practitioner
from fhir.resources.R4B.practitionerrole import PractitionerRole as _PractitionerRole

from parker_atlas.fhir.location import build_location_resource, location_id
from parker_atlas.fhir.organization import (
    build_facility_organization_resource,
    facility_organization_id,
)
from parker_atlas.fhir.practitioner import (
    NPI_IDENTIFIER_SYSTEM,
    build_practitioner_resource,
    practitioner_id,
)
from parker_atlas.fhir.practitioner_role import (
    NUCC_TAXONOMY_SYSTEM,
    build_practitioner_role_resource,
    practitioner_role_id,
)


PRAC_NPI = "1000000012"
FAC_NPI = "2000000010"


def test_practitioner_has_npi_identifier_and_validates():
    r = build_practitioner_resource(
        npi=PRAC_NPI, family="Patel", given="Anika", prefix="Dr."
    )
    _Practitioner.model_validate(r)
    assert r["id"] == practitioner_id(PRAC_NPI)
    assert r["identifier"][0]["system"] == NPI_IDENTIFIER_SYSTEM
    assert r["identifier"][0]["value"] == PRAC_NPI
    assert r["name"][0]["family"] == "Patel"


def test_practitioner_id_is_stable():
    a = build_practitioner_resource(npi=PRAC_NPI, family="X", given="Y")
    b = build_practitioner_resource(npi=PRAC_NPI, family="Z", given="W")
    assert a["id"] == b["id"]


def test_location_validates_and_references_managing_org():
    org_url = "urn:uuid:" + facility_organization_id(FAC_NPI)
    r = build_location_resource(
        facility_npi=FAC_NPI,
        location_name="Main Campus",
        location_type_code="HOSP",
        location_type_display="Hospital",
        line="1 Atlas Way",
        city="Boston",
        state="MA",
        postal_code="02118",
        facility_organization_fullurl=org_url,
    )
    _Location.model_validate(r)
    assert r["id"] == location_id(facility_npi=FAC_NPI, location_name="Main Campus")
    assert r["managingOrganization"]["reference"] == org_url
    assert r["address"]["state"] == "MA"


def test_practitioner_role_links_practitioner_and_org_with_taxonomy():
    prac_url = "urn:uuid:" + practitioner_id(PRAC_NPI)
    org_url = "urn:uuid:" + facility_organization_id(FAC_NPI)
    r = build_practitioner_role_resource(
        practitioner_npi=PRAC_NPI,
        facility_npi=FAC_NPI,
        taxonomy_code="207R00000X",
        taxonomy_display="Internal Medicine",
        practitioner_fullurl=prac_url,
        facility_organization_fullurl=org_url,
    )
    _PractitionerRole.model_validate(r)
    assert r["id"] == practitioner_role_id(
        practitioner_npi=PRAC_NPI,
        facility_npi=FAC_NPI,
        taxonomy_code="207R00000X",
    )
    assert r["practitioner"]["reference"] == prac_url
    assert r["organization"]["reference"] == org_url
    assert r["specialty"][0]["coding"][0]["system"] == NUCC_TAXONOMY_SYSTEM
    assert r["specialty"][0]["coding"][0]["code"] == "207R00000X"


def test_facility_org_has_npi_identifier():
    r = build_facility_organization_resource(npi=FAC_NPI, name="Parker Atlas General")
    assert r["identifier"][0]["system"] == NPI_IDENTIFIER_SYSTEM
    assert r["identifier"][0]["value"] == FAC_NPI


@pytest.mark.parametrize(
    "kwargs",
    [
        {"facility_npi": "A", "location_name": "X"},
        {"facility_npi": "A", "location_name": "Y"},
        {"facility_npi": "B", "location_name": "X"},
    ],
)
def test_location_ids_are_unique_per_facility_and_name(kwargs):
    other = {"facility_npi": "A", "location_name": "X"}
    if kwargs == other:
        return
    assert location_id(**kwargs) != location_id(**other)

"""Coverage / payer Organization / InsurancePlan builder tests."""

from __future__ import annotations

import pytest

from parker_atlas.fhir.coverage import (
    PAYER_TYPE_TO_SOPT,
    SOPT_SYSTEM,
    US_CORE_COVERAGE_PROFILE,
    build_coverage_resource,
    coverage_id,
    subscriber_id,
)
from parker_atlas.fhir.insurance_plan import (
    build_insurance_plan_resource,
    insurance_plan_id,
)
from parker_atlas.fhir.organization import (
    NPI_IDENTIFIER_SYSTEM,
    US_CORE_ORGANIZATION_PROFILE,
    build_facility_organization_resource,
    build_payer_organization_resource,
    payer_organization_id,
)
from parker_atlas.gpx import GPX, Allocator, Category


@pytest.fixture
def gpx() -> GPX:
    return Allocator(Category.SYNTHETIC).allocate()


def test_payer_organization_id_is_deterministic() -> None:
    a = payer_organization_id("medicare-ffs")
    b = payer_organization_id("medicare-ffs")
    c = payer_organization_id("medicaid-state-syn")
    assert a == b
    assert a != c


def test_payer_organization_claims_us_core_profile() -> None:
    org = build_payer_organization_resource(
        payer_id="medicare-ffs", name="Medicare FFS"
    )
    assert US_CORE_ORGANIZATION_PROFILE in org["meta"]["profile"]
    assert org["type"][0]["coding"][0]["code"] == "pay"
    assert org["identifier"][0]["value"] == "medicare-ffs"


def test_facility_organization_uses_npi_identifier_system() -> None:
    org = build_facility_organization_resource(
        npi="1234567893", name="Synthetic General Hospital"
    )
    assert org["identifier"][0]["system"] == NPI_IDENTIFIER_SYSTEM
    assert org["identifier"][0]["value"] == "1234567893"


def test_insurance_plan_id_is_payer_scoped() -> None:
    a = insurance_plan_id("commercial-syn-blue")
    b = insurance_plan_id("commercial-syn-blue")
    c = insurance_plan_id("commercial-syn-aetna")
    assert a == b and a != c


def test_insurance_plan_links_to_payer_organization() -> None:
    plan = build_insurance_plan_resource(
        payer_id="commercial-syn-blue",
        payer_type="commercial",
        plan_name="Synthetic Blue Plan",
        payer_organization_fullurl="urn:uuid:fake-org",
    )
    assert plan["ownedBy"]["reference"] == "urn:uuid:fake-org"
    assert plan["status"] == "active"


def test_coverage_subscriber_id_is_stable_per_gpx_and_payer(gpx: GPX) -> None:
    a = subscriber_id(gpx, "medicare-ffs")
    b = subscriber_id(gpx, "medicare-ffs")
    c = subscriber_id(gpx, "medicaid-state-syn")
    assert a == b
    assert a != c
    assert a.startswith("SYN-")


def test_coverage_claims_us_core_profile_and_sopt(gpx: GPX) -> None:
    cov = build_coverage_resource(
        gpx=gpx,
        patient_fullurl="urn:uuid:pt",
        payer_id="medicare-ffs",
        payer_type="medicare",
        payer_organization_fullurl="urn:uuid:org",
    )
    assert US_CORE_COVERAGE_PROFILE in cov["meta"]["profile"]
    assert cov["type"]["coding"][0]["system"] == SOPT_SYSTEM
    assert cov["type"]["coding"][0]["code"] == PAYER_TYPE_TO_SOPT["medicare"][0]
    assert cov["beneficiary"]["reference"] == "urn:uuid:pt"
    assert cov["payor"][0]["reference"] == "urn:uuid:org"
    assert cov["relationship"]["coding"][0]["code"] == "self"


def test_coverage_id_is_stable(gpx: GPX) -> None:
    a = coverage_id(gpx, "medicare-ffs")
    b = coverage_id(gpx, "medicare-ffs")
    assert a == b


def test_coverage_class_only_populated_when_plan_present(gpx: GPX) -> None:
    cov_no_plan = build_coverage_resource(
        gpx=gpx,
        patient_fullurl="urn:uuid:pt",
        payer_id="commercial-syn-blue",
        payer_type="commercial",
        payer_organization_fullurl="urn:uuid:org",
    )
    assert "class" not in cov_no_plan
    cov_with_plan = build_coverage_resource(
        gpx=gpx,
        patient_fullurl="urn:uuid:pt",
        payer_id="commercial-syn-blue",
        payer_type="commercial",
        payer_organization_fullurl="urn:uuid:org",
        insurance_plan_fullurl="urn:uuid:plan",
    )
    assert cov_with_plan["class"][0]["value"] == "commercial-syn-blue"

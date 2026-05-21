"""FHIR builders for claims and newly covered US Core profiles."""

from __future__ import annotations

from datetime import date

from fhir.resources.R4B.allergyintolerance import AllergyIntolerance
from fhir.resources.R4B.claim import Claim
from fhir.resources.R4B.diagnosticreport import DiagnosticReport
from fhir.resources.R4B.explanationofbenefit import ExplanationOfBenefit
from fhir.resources.R4B.immunization import Immunization

from parker_atlas.fhir.allergy_intolerance import (
    US_CORE_ALLERGY_INTOLERANCE_PROFILE,
    build_allergy_intolerance_resource,
)
from parker_atlas.fhir.claim import (
    CPT_SYSTEM,
    build_claim_resource,
    build_explanation_of_benefit_resource,
)
from parker_atlas.fhir.diagnostic_report import (
    US_CORE_DIAGNOSTIC_REPORT_LAB_PROFILE,
    build_diagnostic_report_resource,
)
from parker_atlas.fhir.immunization import (
    US_CORE_IMMUNIZATION_PROFILE,
    build_immunization_resource,
)
from parker_atlas.gpx import Allocator, Category
from parker_atlas.modules import Coding


def _gpx():
    return Allocator(Category.SYNTHETIC).allocate()


def test_allergy_intolerance_builder_claims_us_core_profile() -> None:
    r = build_allergy_intolerance_resource(
        _gpx(),
        "urn:uuid:pt",
        "penicillin",
        code=Coding(
            "http://www.nlm.nih.gov/research/umls/rxnorm",
            "7980",
            "Penicillin",
        ),
        recorded_date=date(2026, 1, 1),
    )
    AllergyIntolerance.model_validate(r)
    assert US_CORE_ALLERGY_INTOLERANCE_PROFILE in r["meta"]["profile"]
    assert r["patient"]["reference"] == "urn:uuid:pt"


def test_immunization_builder_claims_us_core_profile() -> None:
    r = build_immunization_resource(
        _gpx(),
        "urn:uuid:pt",
        "flu",
        vaccine_code=Coding("http://hl7.org/fhir/sid/cvx", "140", "Influenza"),
        occurrence=date(2026, 1, 1),
        encounter_fullurl="urn:uuid:enc",
    )
    Immunization.model_validate(r)
    assert US_CORE_IMMUNIZATION_PROFILE in r["meta"]["profile"]
    assert r["encounter"]["reference"] == "urn:uuid:enc"


def test_diagnostic_report_references_observations() -> None:
    r = build_diagnostic_report_resource(
        _gpx(),
        "urn:uuid:pt",
        "lipids",
        code=Coding("http://loinc.org", "24331-1", "Lipid panel"),
        effective=date(2026, 1, 1),
        result_fullurls=("urn:uuid:obs1", "urn:uuid:obs2"),
        conclusion="Synthetic lipid panel.",
    )
    DiagnosticReport.model_validate(r)
    assert US_CORE_DIAGNOSTIC_REPORT_LAB_PROFILE in r["meta"]["profile"]
    assert [x["reference"] for x in r["result"]] == ["urn:uuid:obs1", "urn:uuid:obs2"]


def test_claim_and_eob_pair_use_cpt_and_adjudication() -> None:
    gpx = _gpx()
    claim = build_claim_resource(
        gpx,
        "urn:uuid:pt",
        "urn:uuid:enc",
        "urn:uuid:cov",
        encounter_id_value="enc-id",
        encounter_class="AMB",
        created=date(2026, 1, 1),
    )
    eob = build_explanation_of_benefit_resource(
        gpx,
        "urn:uuid:pt",
        "urn:uuid:enc",
        "urn:uuid:cov",
        "urn:uuid:claim",
        encounter_id_value="enc-id",
        encounter_class="AMB",
        payer_type="commercial",
        created=date(2026, 1, 1),
    )
    Claim.model_validate(claim)
    ExplanationOfBenefit.model_validate(eob)
    assert claim["item"][0]["productOrService"]["coding"][0]["system"] == CPT_SYSTEM
    assert eob["claim"]["reference"] == "urn:uuid:claim"
    assert eob["item"][0]["adjudication"]

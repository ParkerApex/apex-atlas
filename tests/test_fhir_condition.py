"""Tests for the FHIR Condition resource builder."""

from __future__ import annotations

from fhir.resources.R4B.condition import Condition

from parker_atlas.fhir.bundle import fullurl_for_gpx
from parker_atlas.fhir.condition import (
    US_CORE_CONDITION_PL_PROFILE,
    build_condition_resource,
    condition_id,
)
from parker_atlas.gpx import GPX, Category
from parker_atlas.modules.runtime import Coding


def _sample_gpx() -> GPX:
    return GPX.mint(Category.SYNTHETIC, 1)


def _sample_code() -> Coding:
    return Coding(
        system="http://snomed.info/sct", code="59621000", display="Essential hypertension"
    )


def test_condition_validates_against_fhir_resources_model():
    gpx = _sample_gpx()
    res = build_condition_resource(
        gpx=gpx,
        patient_fullurl=fullurl_for_gpx(gpx),
        condition_spec_id="essential_hypertension",
        code=_sample_code(),
    )
    Condition.model_validate(res)


def test_condition_has_required_us_core_elements():
    gpx = _sample_gpx()
    res = build_condition_resource(
        gpx=gpx,
        patient_fullurl=fullurl_for_gpx(gpx),
        condition_spec_id="essential_hypertension",
        code=_sample_code(),
    )
    for field in ("clinicalStatus", "verificationStatus", "category", "code", "subject"):
        assert res.get(field), f"missing required field: {field}"


def test_condition_subject_references_patient_fullurl():
    gpx = _sample_gpx()
    patient_url = fullurl_for_gpx(gpx)
    res = build_condition_resource(
        gpx=gpx,
        patient_fullurl=patient_url,
        condition_spec_id="essential_hypertension",
        code=_sample_code(),
    )
    assert res["subject"]["reference"] == patient_url


def test_condition_carries_us_core_profile_claim():
    gpx = _sample_gpx()
    res = build_condition_resource(
        gpx=gpx,
        patient_fullurl=fullurl_for_gpx(gpx),
        condition_spec_id="essential_hypertension",
        code=_sample_code(),
    )
    assert US_CORE_CONDITION_PL_PROFILE in res["meta"]["profile"]


def test_condition_carries_htest_tag():
    gpx = _sample_gpx()
    res = build_condition_resource(
        gpx=gpx,
        patient_fullurl=fullurl_for_gpx(gpx),
        condition_spec_id="essential_hypertension",
        code=_sample_code(),
    )
    tags = res["meta"]["tag"]
    assert any(t["code"] == "HTEST" for t in tags)


def test_condition_id_is_deterministic():
    gpx = _sample_gpx()
    assert condition_id(gpx, "x") == condition_id(gpx, "x")
    assert condition_id(gpx, "x") != condition_id(gpx, "y")


def test_condition_id_differs_by_patient():
    g1 = GPX.mint(Category.SYNTHETIC, 1)
    g2 = GPX.mint(Category.SYNTHETIC, 2)
    assert condition_id(g1, "essential_hypertension") != condition_id(
        g2, "essential_hypertension"
    )

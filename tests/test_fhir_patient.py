"""Tests for the FHIR Patient resource builder and Bundle wrapper."""

from __future__ import annotations

import random
from datetime import date

from fhir.resources.R4B.bundle import Bundle
from fhir.resources.R4B.patient import Patient

from parker_atlas.core.demographics import sample_demographics
from parker_atlas.fhir.bundle import fullurl_for_gpx, patient_bundle
from parker_atlas.fhir.patient import (
    US_CORE_BIRTHSEX_URL,
    US_CORE_ETHNICITY_URL,
    US_CORE_PATIENT_PROFILE,
    US_CORE_RACE_URL,
    build_patient_resource,
)
from parker_atlas.gpx import GPX, SYSTEM_URI, Category


def _fresh_demo(seed: int = 0):
    rng = random.Random(seed)
    return sample_demographics(rng, today=date(2026, 1, 1))


def test_patient_validates_against_fhir_resources_model():
    gpx = GPX.mint(Category.SYNTHETIC, 1)
    demo = _fresh_demo()
    resource = build_patient_resource(gpx, demo)
    # build_patient_resource already validates, but assert here too.
    Patient.model_validate(resource)


def test_patient_has_required_us_core_fields():
    gpx = GPX.mint(Category.SYNTHETIC, 42)
    demo = _fresh_demo()
    resource = build_patient_resource(gpx, demo)

    assert resource["resourceType"] == "Patient"
    assert resource["gender"] in ("male", "female")
    assert resource["birthDate"]
    assert resource["name"][0]["family"]
    assert resource["name"][0]["given"]


def test_patient_carries_gpx_identifier():
    gpx = GPX.mint(Category.SYNTHETIC, 99)
    resource = build_patient_resource(gpx, _fresh_demo())

    identifiers = resource["identifier"]
    assert len(identifiers) == 1
    assert identifiers[0]["system"] == SYSTEM_URI
    assert identifiers[0]["value"] == str(gpx)


def test_patient_claims_us_core_profile():
    gpx = GPX.mint(Category.SYNTHETIC, 1)
    resource = build_patient_resource(gpx, _fresh_demo())
    assert US_CORE_PATIENT_PROFILE in resource["meta"]["profile"]


def test_patient_is_marked_synthetic_via_htest_tag():
    gpx = GPX.mint(Category.SYNTHETIC, 1)
    resource = build_patient_resource(gpx, _fresh_demo())
    tags = resource["meta"]["tag"]
    assert any(t["code"] == "HTEST" for t in tags)


def test_patient_carries_race_ethnicity_and_birthsex_extensions():
    gpx = GPX.mint(Category.SYNTHETIC, 1)
    resource = build_patient_resource(gpx, _fresh_demo())

    ext_urls = {e["url"] for e in resource["extension"]}
    assert US_CORE_RACE_URL in ext_urls
    assert US_CORE_ETHNICITY_URL in ext_urls
    assert US_CORE_BIRTHSEX_URL in ext_urls


def test_bundle_validates_and_wraps_patient():
    gpx = GPX.mint(Category.SYNTHETIC, 1)
    resource = build_patient_resource(gpx, _fresh_demo())
    bundle = patient_bundle(gpx, resource)

    Bundle.model_validate(bundle)
    assert bundle["type"] == "transaction"
    assert len(bundle["entry"]) == 1
    assert bundle["entry"][0]["resource"] == resource
    assert bundle["entry"][0]["request"]["method"] == "POST"


def test_fullurl_is_stable_for_same_gpx():
    gpx = GPX.mint(Category.SYNTHETIC, 500)
    assert fullurl_for_gpx(gpx) == fullurl_for_gpx(gpx)


def test_fullurl_differs_across_gpx():
    g1 = GPX.mint(Category.SYNTHETIC, 1)
    g2 = GPX.mint(Category.SYNTHETIC, 2)
    assert fullurl_for_gpx(g1) != fullurl_for_gpx(g2)

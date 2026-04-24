"""Tests for the FHIR MedicationRequest resource builder."""

from __future__ import annotations

from datetime import date, datetime

import pytest
from fhir.resources.R4B.medicationrequest import MedicationRequest

from parker_atlas.fhir.bundle import fullurl_for_gpx
from parker_atlas.fhir.medication_request import (
    US_CORE_MEDICATION_REQUEST_PROFILE,
    build_medication_request_resource,
    medication_request_id,
)
from parker_atlas.gpx import GPX, Category
from parker_atlas.modules.runtime import Coding


def _sample_gpx() -> GPX:
    return GPX.mint(Category.SYNTHETIC, 1)


def _lisinopril() -> Coding:
    return Coding(
        system="http://www.nlm.nih.gov/research/umls/rxnorm",
        code="197361",
        display="Lisinopril 10 MG Oral Tablet",
    )


class TestBuildMedicationRequest:
    def test_minimal_request_validates(self):
        gpx = _sample_gpx()
        med = build_medication_request_resource(
            gpx,
            fullurl_for_gpx(gpx),
            "htn_lisinopril_start",
            medication_code=_lisinopril(),
            authored_on=date(2026, 4, 24),
        )
        MedicationRequest.model_validate(med)
        assert US_CORE_MEDICATION_REQUEST_PROFILE in med["meta"]["profile"]
        assert med["status"] == "active"
        assert med["intent"] == "order"
        assert med["medicationCodeableConcept"]["coding"][0]["code"] == "197361"

    def test_status_and_intent_can_be_overridden(self):
        gpx = _sample_gpx()
        med = build_medication_request_resource(
            gpx,
            fullurl_for_gpx(gpx),
            "plan_only",
            medication_code=_lisinopril(),
            authored_on=date(2026, 4, 24),
            status="draft",
            intent="plan",
        )
        assert med["status"] == "draft"
        assert med["intent"] == "plan"

    def test_reason_code_is_emitted_when_provided(self):
        gpx = _sample_gpx()
        med = build_medication_request_resource(
            gpx,
            fullurl_for_gpx(gpx),
            "for_htn",
            medication_code=_lisinopril(),
            authored_on=date(2026, 4, 24),
            reason_code=Coding(
                "http://snomed.info/sct",
                "59621000",
                "Essential hypertension",
            ),
        )
        assert med["reasonCode"][0]["coding"][0]["code"] == "59621000"

    def test_encounter_reference_is_emitted_when_provided(self):
        gpx = _sample_gpx()
        med = build_medication_request_resource(
            gpx,
            fullurl_for_gpx(gpx),
            "x",
            medication_code=_lisinopril(),
            authored_on=date(2026, 4, 24),
            encounter_fullurl="urn:uuid:some-encounter-fullurl",
        )
        assert med["encounter"]["reference"] == "urn:uuid:some-encounter-fullurl"

    def test_minimal_request_omits_reason_and_encounter(self):
        gpx = _sample_gpx()
        med = build_medication_request_resource(
            gpx,
            fullurl_for_gpx(gpx),
            "x",
            medication_code=_lisinopril(),
            authored_on=date(2026, 4, 24),
        )
        assert "reasonCode" not in med
        assert "encounter" not in med

    def test_authored_on_datetime_gets_utc_stamp(self):
        gpx = _sample_gpx()
        med = build_medication_request_resource(
            gpx,
            fullurl_for_gpx(gpx),
            "x",
            medication_code=_lisinopril(),
            authored_on=datetime(2026, 4, 24, 15, 30),
        )
        assert med["authoredOn"] == "2026-04-24T15:30:00Z"

    def test_carries_htest_tag(self):
        gpx = _sample_gpx()
        med = build_medication_request_resource(
            gpx,
            fullurl_for_gpx(gpx),
            "x",
            medication_code=_lisinopril(),
            authored_on=date(2026, 4, 24),
        )
        tags = med["meta"]["tag"]
        assert any(t["code"] == "HTEST" for t in tags)

    def test_subject_references_patient_fullurl(self):
        gpx = _sample_gpx()
        url = fullurl_for_gpx(gpx)
        med = build_medication_request_resource(
            gpx,
            url,
            "x",
            medication_code=_lisinopril(),
            authored_on=date(2026, 4, 24),
        )
        assert med["subject"]["reference"] == url


class TestInputValidation:
    def test_rejects_unknown_status(self):
        gpx = _sample_gpx()
        with pytest.raises(ValueError, match="unsupported status"):
            build_medication_request_resource(
                gpx,
                fullurl_for_gpx(gpx),
                "x",
                medication_code=_lisinopril(),
                authored_on=date(2026, 4, 24),
                status="nope",
            )

    def test_rejects_unknown_intent(self):
        gpx = _sample_gpx()
        with pytest.raises(ValueError, match="unsupported intent"):
            build_medication_request_resource(
                gpx,
                fullurl_for_gpx(gpx),
                "x",
                medication_code=_lisinopril(),
                authored_on=date(2026, 4, 24),
                intent="nope",
            )


class TestIdDeterminism:
    def test_id_is_stable(self):
        gpx = _sample_gpx()
        assert medication_request_id(gpx, "x") == medication_request_id(gpx, "x")

    def test_id_differs_by_spec(self):
        gpx = _sample_gpx()
        assert medication_request_id(gpx, "a") != medication_request_id(gpx, "b")

    def test_id_differs_across_patients(self):
        g1 = GPX.mint(Category.SYNTHETIC, 1)
        g2 = GPX.mint(Category.SYNTHETIC, 2)
        assert medication_request_id(g1, "x") != medication_request_id(g2, "x")

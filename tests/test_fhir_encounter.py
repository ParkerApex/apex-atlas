"""Tests for the FHIR Encounter resource builder."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from fhir.resources.R4B.encounter import Encounter

from parker_atlas.fhir.bundle import fullurl_for_gpx
from parker_atlas.fhir.encounter import (
    ENCOUNTER_CLASSES,
    US_CORE_ENCOUNTER_PROFILE,
    build_encounter_resource,
    encounter_id,
)
from parker_atlas.gpx import GPX, Category
from parker_atlas.modules.runtime import Coding


def _sample_gpx() -> GPX:
    return GPX.mint(Category.SYNTHETIC, 1)


def _checkup_type() -> Coding:
    return Coding(
        system="http://snomed.info/sct",
        code="185349003",
        display="Encounter for check up",
    )


class TestBuildEncounter:
    def test_ambulatory_encounter_validates(self):
        gpx = _sample_gpx()
        enc = build_encounter_resource(
            gpx,
            fullurl_for_gpx(gpx),
            "annual_visit_2026",
            class_code="AMB",
            type_code=_checkup_type(),
            period_start=date(2026, 4, 24),
            period_end=date(2026, 4, 24),
        )
        Encounter.model_validate(enc)
        assert enc["class"]["code"] == "AMB"
        assert US_CORE_ENCOUNTER_PROFILE in enc["meta"]["profile"]

    def test_inpatient_encounter_validates(self):
        gpx = _sample_gpx()
        enc = build_encounter_resource(
            gpx,
            fullurl_for_gpx(gpx),
            "admission_2026",
            class_code="IMP",
            type_code=Coding(
                "http://snomed.info/sct",
                "32485007",
                "Hospital admission",
            ),
            period_start=date(2026, 4, 20),
            period_end=date(2026, 4, 25),
        )
        Encounter.model_validate(enc)
        assert enc["class"]["code"] == "IMP"

    def test_open_ended_encounter_omits_end(self):
        gpx = _sample_gpx()
        enc = build_encounter_resource(
            gpx,
            fullurl_for_gpx(gpx),
            "in_progress",
            class_code="IMP",
            type_code=_checkup_type(),
            period_start=date(2026, 4, 24),
            status="in-progress",
        )
        assert "end" not in enc["period"]
        assert enc["status"] == "in-progress"

    def test_datetime_start_gets_utc_stamp(self):
        gpx = _sample_gpx()
        enc = build_encounter_resource(
            gpx,
            fullurl_for_gpx(gpx),
            "with_time",
            class_code="AMB",
            type_code=_checkup_type(),
            period_start=datetime(2026, 4, 24, 9, 0),
            period_end=datetime(2026, 4, 24, 9, 30),
        )
        assert enc["period"]["start"] == "2026-04-24T09:00:00Z"
        assert enc["period"]["end"] == "2026-04-24T09:30:00Z"

    def test_tz_aware_datetime_preserves_offset(self):
        gpx = _sample_gpx()
        tz = timezone.utc
        enc = build_encounter_resource(
            gpx,
            fullurl_for_gpx(gpx),
            "with_tz",
            class_code="AMB",
            type_code=_checkup_type(),
            period_start=datetime(2026, 4, 24, 9, 0, tzinfo=tz),
        )
        assert enc["period"]["start"] == "2026-04-24T09:00:00+00:00"

    def test_encounter_carries_reason_code_when_provided(self):
        gpx = _sample_gpx()
        enc = build_encounter_resource(
            gpx,
            fullurl_for_gpx(gpx),
            "htn_followup",
            class_code="AMB",
            type_code=_checkup_type(),
            period_start=date(2026, 4, 24),
            reason_code=Coding(
                "http://snomed.info/sct",
                "38341003",
                "Hypertensive disorder",
            ),
        )
        assert enc["reasonCode"][0]["coding"][0]["code"] == "38341003"

    def test_encounter_omits_reason_code_when_not_provided(self):
        gpx = _sample_gpx()
        enc = build_encounter_resource(
            gpx,
            fullurl_for_gpx(gpx),
            "x",
            class_code="AMB",
            type_code=_checkup_type(),
            period_start=date(2026, 4, 24),
        )
        assert "reasonCode" not in enc

    def test_carries_identifier_and_htest_tag(self):
        gpx = _sample_gpx()
        enc = build_encounter_resource(
            gpx,
            fullurl_for_gpx(gpx),
            "x",
            class_code="AMB",
            type_code=_checkup_type(),
            period_start=date(2026, 4, 24),
        )
        assert enc["identifier"]
        tags = enc["meta"]["tag"]
        assert any(t["code"] == "HTEST" for t in tags)

    def test_subject_references_patient_fullurl(self):
        gpx = _sample_gpx()
        url = fullurl_for_gpx(gpx)
        enc = build_encounter_resource(
            gpx,
            url,
            "x",
            class_code="AMB",
            type_code=_checkup_type(),
            period_start=date(2026, 4, 24),
        )
        assert enc["subject"]["reference"] == url


class TestInputValidation:
    def test_rejects_unknown_encounter_class(self):
        gpx = _sample_gpx()
        with pytest.raises(ValueError, match="unsupported encounter class"):
            build_encounter_resource(
                gpx,
                fullurl_for_gpx(gpx),
                "x",
                class_code="NOPE",
                type_code=_checkup_type(),
                period_start=date(2026, 4, 24),
            )

    def test_supported_classes_includes_core_set(self):
        for c in ("AMB", "IMP", "EMER", "HH", "VR"):
            assert c in ENCOUNTER_CLASSES


class TestIdDeterminism:
    def test_encounter_id_is_stable(self):
        gpx = _sample_gpx()
        assert encounter_id(gpx, "x") == encounter_id(gpx, "x")

    def test_encounter_id_differs_by_spec(self):
        gpx = _sample_gpx()
        assert encounter_id(gpx, "a") != encounter_id(gpx, "b")

    def test_encounter_id_differs_across_patients(self):
        g1 = GPX.mint(Category.SYNTHETIC, 1)
        g2 = GPX.mint(Category.SYNTHETIC, 2)
        assert encounter_id(g1, "x") != encounter_id(g2, "x")

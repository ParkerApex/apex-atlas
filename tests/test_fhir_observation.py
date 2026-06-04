"""Tests for the FHIR Observation resource builder."""

from __future__ import annotations

from datetime import date, datetime

import pytest
from fhir.resources.R4B.observation import Observation

from parker_atlas.fhir.bundle import fullurl_for_gpx
from parker_atlas.fhir.observation import (
    BLOOD_PRESSURE_PANEL_LOINC,
    US_CORE_BLOOD_PRESSURE_PROFILE,
    US_CORE_LAB_RESULT_PROFILE,
    US_CORE_VITAL_SIGNS_PROFILE,
    ObservationComponent,
    Quantity,
    build_observation_resource,
    observation_id,
)
from parker_atlas.gpx import GPX, Category
from parker_atlas.modules.runtime import Coding


def _sample_gpx() -> GPX:
    return GPX.mint(Category.SYNTHETIC, 1)


def _sample_lab_code() -> Coding:
    return Coding(
        system="http://loinc.org", code="4548-4", display="Hemoglobin A1c"
    )


def _sample_vital_code() -> Coding:
    return Coding(
        system="http://loinc.org", code="29463-7", display="Body weight"
    )


def _sample_bp_code() -> Coding:
    return Coding(
        system="http://loinc.org",
        code=BLOOD_PRESSURE_PANEL_LOINC,
        display="Blood pressure panel with all children optional",
    )


class TestSingleValueObservations:
    def test_lab_result_validates_and_claims_profile(self):
        gpx = _sample_gpx()
        obs = build_observation_resource(
            gpx,
            fullurl_for_gpx(gpx),
            "diabetes_a1c",
            category="laboratory",
            code=_sample_lab_code(),
            effective=date(2026, 4, 24),
            value=Quantity(value=7.2, unit="%"),
        )
        Observation.model_validate(obs)
        assert obs["category"][0]["coding"][0]["code"] == "laboratory"
        assert US_CORE_LAB_RESULT_PROFILE in obs["meta"]["profile"]
        assert obs["valueQuantity"]["value"] == 7.2

    def test_vital_sign_picks_vital_signs_profile(self):
        gpx = _sample_gpx()
        obs = build_observation_resource(
            gpx,
            fullurl_for_gpx(gpx),
            "weight_at_visit_1",
            category="vital-signs",
            code=_sample_vital_code(),
            effective=date(2026, 4, 24),
            value=Quantity(value=82.3, unit="kg"),
        )
        Observation.model_validate(obs)
        assert US_CORE_VITAL_SIGNS_PROFILE in obs["meta"]["profile"]

    def test_datetime_effective_preserves_time(self):
        gpx = _sample_gpx()
        when = datetime(2026, 4, 24, 10, 30)
        obs = build_observation_resource(
            gpx,
            fullurl_for_gpx(gpx),
            "observation_with_time",
            category="laboratory",
            code=_sample_lab_code(),
            effective=when,
            value=Quantity(value=100.0, unit="mg/dL"),
        )
        # Naive datetimes are stamped as UTC to satisfy FHIR R4's dateTime regex.
        assert obs["effectiveDateTime"] == "2026-04-24T10:30:00Z"

    def test_ucum_code_defaults_to_unit_when_omitted(self):
        gpx = _sample_gpx()
        obs = build_observation_resource(
            gpx,
            fullurl_for_gpx(gpx),
            "obs",
            category="laboratory",
            code=_sample_lab_code(),
            effective=date(2026, 4, 24),
            value=Quantity(value=5.5, unit="mmol/L"),  # code omitted
        )
        assert obs["valueQuantity"]["code"] == "mmol/L"

    def test_observation_subject_references_patient_fullurl(self):
        gpx = _sample_gpx()
        url = fullurl_for_gpx(gpx)
        obs = build_observation_resource(
            gpx,
            url,
            "obs",
            category="laboratory",
            code=_sample_lab_code(),
            effective=date(2026, 4, 24),
            value=Quantity(value=1.0, unit="mg/dL"),
        )
        assert obs["subject"]["reference"] == url

    def test_observation_carries_htest_tag(self):
        gpx = _sample_gpx()
        obs = build_observation_resource(
            gpx,
            fullurl_for_gpx(gpx),
            "obs",
            category="laboratory",
            code=_sample_lab_code(),
            effective=date(2026, 4, 24),
            value=Quantity(value=1.0, unit="mg/dL"),
        )
        tags = obs["meta"]["tag"]
        assert any(t["code"] == "HTEST" for t in tags)


class TestMultiComponentObservations:
    def test_blood_pressure_uses_bp_profile_and_two_components(self):
        gpx = _sample_gpx()
        obs = build_observation_resource(
            gpx,
            fullurl_for_gpx(gpx),
            "htn_bp_visit_1",
            category="vital-signs",
            code=_sample_bp_code(),
            effective=date(2026, 4, 24),
            components=(
                ObservationComponent(
                    code=Coding("http://loinc.org", "8480-6", "Systolic"),
                    value=Quantity(value=148.0, unit="mm[Hg]"),
                ),
                ObservationComponent(
                    code=Coding("http://loinc.org", "8462-4", "Diastolic"),
                    value=Quantity(value=94.0, unit="mm[Hg]"),
                ),
            ),
        )
        Observation.model_validate(obs)
        assert US_CORE_BLOOD_PRESSURE_PROFILE in obs["meta"]["profile"]
        assert len(obs["component"]) == 2
        assert obs["component"][0]["valueQuantity"]["value"] == 148.0
        assert obs["component"][1]["valueQuantity"]["value"] == 94.0


class TestInputValidation:
    def test_rejects_missing_value_and_components(self):
        gpx = _sample_gpx()
        with pytest.raises(ValueError, match="either `value` or `components`"):
            build_observation_resource(
                gpx,
                fullurl_for_gpx(gpx),
                "obs",
                category="laboratory",
                code=_sample_lab_code(),
                effective=date(2026, 4, 24),
            )

    def test_rejects_both_value_and_components(self):
        gpx = _sample_gpx()
        with pytest.raises(ValueError, match="XOR"):
            build_observation_resource(
                gpx,
                fullurl_for_gpx(gpx),
                "obs",
                category="vital-signs",
                code=_sample_bp_code(),
                effective=date(2026, 4, 24),
                value=Quantity(value=100.0, unit="mg/dL"),
                components=(
                    ObservationComponent(
                        code=Coding("http://loinc.org", "8480-6", "Systolic"),
                        value=Quantity(value=148.0, unit="mm[Hg]"),
                    ),
                ),
            )

    def test_rejects_unsupported_category(self):
        gpx = _sample_gpx()
        with pytest.raises(ValueError, match="unsupported category"):
            build_observation_resource(
                gpx,
                fullurl_for_gpx(gpx),
                "obs",
                category="not-a-real-category",  # outside the HL7 value set
                code=_sample_lab_code(),
                effective=date(2026, 4, 24),
                value=Quantity(value=1.0, unit="mg/dL"),
            )


class TestIdDeterminism:
    def test_observation_id_is_stable_for_same_inputs(self):
        gpx = _sample_gpx()
        assert observation_id(gpx, "x") == observation_id(gpx, "x")

    def test_observation_id_differs_by_spec(self):
        gpx = _sample_gpx()
        assert observation_id(gpx, "a") != observation_id(gpx, "b")

    def test_observation_id_differs_by_patient(self):
        g1 = GPX.mint(Category.SYNTHETIC, 1)
        g2 = GPX.mint(Category.SYNTHETIC, 2)
        assert observation_id(g1, "a") != observation_id(g2, "a")


class TestNonLabVitalCategories:
    """survey / social-history / exam are valid FHIR observation categories that
    real modules emit (PHQ-9, smoking status, exam findings). They must build a
    valid Observation, but claim no US Core profile (we don't conform to one)."""

    def _build(self, category):
        return build_observation_resource(
            _sample_gpx(),
            fullurl_for_gpx(_sample_gpx()),
            f"obs_{category}",
            category=category,
            code=Coding(system="http://loinc.org", code="44249-1", display="PHQ-9 total score"),
            effective=date(2024, 1, 1),
            value=Quantity(value=12, unit="{score}"),
        )

    @pytest.mark.parametrize("category", ["survey", "social-history", "exam"])
    def test_builds_valid_observation(self, category):
        resource = self._build(category)
        Observation.model_validate(resource)
        assert resource["category"][0]["coding"][0]["code"] == category

    @pytest.mark.parametrize("category", ["survey", "social-history", "exam"])
    def test_claims_no_us_core_profile(self, category):
        # No US Core profile for these categories — meta carries only the tag.
        resource = self._build(category)
        assert "profile" not in resource["meta"]
        assert resource["meta"]["tag"]

    def test_rejects_unknown_category(self):
        with pytest.raises(ValueError, match="unsupported category"):
            self._build("not-a-real-category")

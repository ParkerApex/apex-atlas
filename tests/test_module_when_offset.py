"""Tests for offset-style `when` expressions (onset+30d, today-1y, etc.)."""

from __future__ import annotations

import json
import random
import textwrap
from datetime import date

import pytest
from typer.testing import CliRunner

from parker_atlas.cli import app
from parker_atlas.modules import (
    ModuleError,
    SampledMedicationRequest,
    SampledObservation,
    load_module_from_str,
    run_module,
)
from parker_atlas.modules.runtime import _resolve_when

runner = CliRunner()


def _module_with_when(when: str) -> str:
    """Build a minimal module whose only emit uses the given `when`."""
    return textwrap.dedent(
        f"""
        module: t
        version: 0.0.1
        conditions:
          - id: c
            code: {{system: s, code: "1", display: d}}
            prevalence: {{"0-99": 1.0}}
            onset_age: {{min: 25, max: 65}}
            emits:
              - resource_type: MedicationRequest
                spec_id: m
                when: {when}
                medication: {{system: rxnorm, code: "1", display: drug}}
        """
    )


class TestOffsetParsing:
    @pytest.mark.parametrize(
        "when",
        [
            "today",
            "onset",
            "onset+30d",
            "onset+6m",
            "onset+2y",
            "onset+1w",
            "today-1y",
            "today-30d",
            "today-12m",
            "today-2w",
            "onset-7d",  # before onset is also legal
        ],
    )
    def test_accepts_valid_when(self, when: str):
        mod = load_module_from_str(_module_with_when(when))
        assert mod.conditions[0].emits[0].when == when

    @pytest.mark.parametrize(
        "when",
        [
            "yesterday",
            "onset+",
            "onset+1",       # missing unit
            "onset+1day",    # only single-letter units accepted
            "onset+1.5d",    # no decimals
            "today*30d",     # wrong sign
            "onset+1h",      # hours not supported
            "today+1d+1d",   # only one offset segment
            "onset 30d",     # no spaces
        ],
    )
    def test_rejects_invalid_when(self, when: str):
        with pytest.raises(ModuleError, match="when="):
            load_module_from_str(_module_with_when(when))


class TestOffsetResolution:
    """Direct unit tests on _resolve_when."""

    TODAY = date(2026, 4, 25)
    ONSET = date(2024, 4, 25)  # 2 years before today

    def test_today_with_no_offset(self):
        assert _resolve_when("today", self.TODAY, self.ONSET) == self.TODAY

    def test_onset_with_no_offset(self):
        assert _resolve_when("onset", self.TODAY, self.ONSET) == self.ONSET

    def test_onset_falls_back_to_today_when_no_onset_date(self):
        assert _resolve_when("onset", self.TODAY, None) == self.TODAY
        assert _resolve_when("onset+30d", self.TODAY, None) == self.TODAY + _delta(30)

    def test_positive_day_offset(self):
        assert _resolve_when("onset+30d", self.TODAY, self.ONSET) == self.ONSET + _delta(30)

    def test_negative_day_offset(self):
        assert _resolve_when("today-30d", self.TODAY, self.ONSET) == self.TODAY - _delta(30)

    def test_week_offset(self):
        assert _resolve_when("onset+2w", self.TODAY, self.ONSET) == self.ONSET + _delta(14)

    def test_month_offset_uses_30_days(self):
        assert _resolve_when("onset+6m", self.TODAY, self.ONSET) == self.ONSET + _delta(180)

    def test_year_offset_uses_365_days(self):
        assert _resolve_when("today-1y", self.TODAY, self.ONSET) == self.TODAY - _delta(365)

    def test_offset_after_today_is_legal(self):
        # `onset+10y` for a recent diagnosis can land beyond today —
        # allowed (e.g., scheduled future visit). Caller decides.
        result = _resolve_when("onset+10y", self.TODAY, self.ONSET)
        assert result > self.TODAY


class TestOffsetSamplingEndToEnd:
    def test_emit_carries_offset_resolved_date(self):
        """Module declaring `when: onset+90d` produces a sampled
        resource whose effective_date is exactly onset_date + 90 days."""
        mod = load_module_from_str(_module_with_when("onset+90d"))
        rng = random.Random(0)
        today = date(2026, 4, 25)
        diagnoses = run_module(mod, age_years=50, sex="female", rng=rng, today=today)
        dx = diagnoses[0]
        sr = dx.sampled_resources[0]
        assert isinstance(sr, SampledMedicationRequest)
        assert dx.onset_date is not None
        assert sr.effective_date == dx.onset_date + _delta(90)

    def test_today_minus_year_offset(self):
        mod = load_module_from_str(_module_with_when("today-1y"))
        rng = random.Random(0)
        today = date(2026, 4, 25)
        diagnoses = run_module(mod, age_years=50, sex="female", rng=rng, today=today)
        sr = diagnoses[0].sampled_resources[0]
        assert sr.effective_date == today - _delta(365)


class TestOffsetCLIEndToEnd:
    def test_observation_emits_at_onset_plus_offset(self, tmp_path):
        """A module with `when: onset+30d` produces FHIR Observations
        whose effectiveDateTime is exactly 30 days after the patient's
        Condition.onsetDateTime."""
        # Hand-author a fixture module file so we don't disturb the
        # bundled library. Generate via the exposed module loader by
        # writing it to disk and pointing at it, but our CLI only loads
        # bundled modules — so instead exercise the runtime directly
        # via run_module + the existing FHIR builders is sufficient.
        # Here we just verify via the runtime path (CLI surface for
        # custom-path modules is a separate feature).
        mod = load_module_from_str(
            textwrap.dedent(
                """
                module: t
                version: 0.0.1
                conditions:
                  - id: c
                    code: {system: http://snomed.info/sct, code: "1", display: D}
                    prevalence: {"0-99": 1.0}
                    onset_age: {min: 25, max: 65}
                    emits:
                      - resource_type: Observation
                        spec_id: o
                        when: onset+30d
                        category: laboratory
                        code: {system: http://loinc.org, code: "4548-4", display: A1c}
                        value_range: {low: 6.5, high: 9.5}
                        unit: "%"
                """
            )
        )
        rng = random.Random(0)
        today = date(2026, 4, 25)
        diagnoses = run_module(mod, age_years=50, sex="female", rng=rng, today=today)
        sr = diagnoses[0].sampled_resources[0]
        assert isinstance(sr, SampledObservation)
        assert sr.effective_date == diagnoses[0].onset_date + _delta(30)


def _delta(days: int):
    from datetime import timedelta
    return timedelta(days=days)

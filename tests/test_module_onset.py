"""Tests for module onset_age sampling and Condition.onsetDateTime emission."""

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
    OnsetAgeRange,
    load_module,
    load_module_from_str,
    run_module,
)
from parker_atlas.modules.runtime import _sample_onset_date

runner = CliRunner()


def _module_with_onset(onset_yaml: str) -> str:
    return textwrap.dedent(
        f"""
        module: t
        version: 0.0.1
        conditions:
          - id: c
            code:
              system: http://snomed.info/sct
              code: "1"
              display: Foo
            prevalence:
              "0-99": 1.0
{textwrap.indent(textwrap.dedent(onset_yaml), '            ')}
        """
    )


class TestOnsetAgeParsing:
    def test_parses_onset_age(self):
        mod = load_module_from_str(_module_with_onset("onset_age:\n  min: 30\n  max: 60"))
        cond = mod.conditions[0]
        assert isinstance(cond.onset_age, OnsetAgeRange)
        assert cond.onset_age.min == 30
        assert cond.onset_age.max == 60

    def test_omitting_onset_age_leaves_it_none(self):
        mod = load_module_from_str(_module_with_onset(""))
        assert mod.conditions[0].onset_age is None

    def test_rejects_inverted_bounds(self):
        with pytest.raises(ModuleError, match="onset_age.max"):
            load_module_from_str(_module_with_onset("onset_age:\n  min: 60\n  max: 30"))

    def test_rejects_negative_min(self):
        with pytest.raises(ModuleError, match="must be >= 0"):
            load_module_from_str(_module_with_onset("onset_age:\n  min: -5\n  max: 30"))

    def test_rejects_missing_min(self):
        with pytest.raises(ModuleError, match="onset_age missing"):
            load_module_from_str(_module_with_onset("onset_age:\n  max: 60"))


class TestOnsetSampling:
    def test_onset_date_falls_in_age_range(self):
        rng = random.Random(0)
        today = date(2026, 4, 25)
        for _ in range(50):
            onset = _sample_onset_date(
                OnsetAgeRange(min=30, max=60), current_age=70, today=today, rng=rng
            )
            years_ago = (today - onset).days // 365
            onset_age = 70 - years_ago
            assert 30 <= onset_age <= 60

    def test_patient_too_young_treated_as_just_diagnosed(self):
        rng = random.Random(0)
        today = date(2026, 4, 25)
        # Patient is 20 but module's onset_age is 30-60.
        onset = _sample_onset_date(
            OnsetAgeRange(min=30, max=60), current_age=20, today=today, rng=rng
        )
        assert onset == today

    def test_max_clamped_to_current_age(self):
        rng = random.Random(0)
        today = date(2026, 4, 25)
        # Patient is 35, onset_age range is 25-60. Onset can't be > 35.
        for _ in range(50):
            onset = _sample_onset_date(
                OnsetAgeRange(min=25, max=60), current_age=35, today=today, rng=rng
            )
            years_ago = (today - onset).days // 365
            onset_age = 35 - years_ago
            assert 25 <= onset_age <= 35

    def test_run_module_attaches_onset_date(self):
        mod = load_module_from_str(
            _module_with_onset("onset_age:\n  min: 25\n  max: 65")
        )
        rng = random.Random(0)
        today = date(2026, 4, 25)
        diagnoses = run_module(mod, age_years=50, sex="female", rng=rng, today=today)
        assert len(diagnoses) == 1
        assert diagnoses[0].onset_date is not None
        assert diagnoses[0].onset_date <= today

    def test_run_module_without_onset_age_leaves_onset_date_none(self):
        mod = load_module_from_str(_module_with_onset(""))
        rng = random.Random(0)
        diagnoses = run_module(mod, age_years=50, sex="female", rng=rng)
        assert diagnoses[0].onset_date is None


class TestOnsetEndToEnd:
    def test_hypertension_bundles_carry_onset_datetime(self, tmp_path):
        result = runner.invoke(
            app,
            [
                "generate",
                "--patients", "20",
                "--seed", "42",
                "--module", "hypertension",
                "--out", str(tmp_path),
            ],
        )
        assert result.exit_code == 0, result.output

        hits = 0
        for f in sorted(tmp_path.glob("*.json")):
            data = json.loads(f.read_text())
            for entry in data["entry"]:
                if entry["resource"]["resourceType"] == "Condition":
                    assert "onsetDateTime" in entry["resource"], (
                        f"hypertension Condition missing onsetDateTime in {f.name}"
                    )
                    hits += 1
        assert hits >= 1, "expected at least one hypertensive bundle in 20 patients"

    def test_other_modules_without_onset_age_omit_onset_datetime(self, tmp_path):
        # Diabetes module does not yet declare onset_age (v0.2.0).
        result = runner.invoke(
            app,
            [
                "generate",
                "--patients", "20",
                "--seed", "42",
                "--module", "diabetes",
                "--out", str(tmp_path),
            ],
        )
        assert result.exit_code == 0, result.output

        for f in sorted(tmp_path.glob("*.json")):
            data = json.loads(f.read_text())
            for entry in data["entry"]:
                if entry["resource"]["resourceType"] == "Condition":
                    assert "onsetDateTime" not in entry["resource"], (
                        f"unexpected onsetDateTime on diabetes Condition in {f.name}"
                    )

    def test_onset_dates_are_reproducible_with_seed(self, tmp_path):
        out1, out2 = tmp_path / "a", tmp_path / "b"
        for path in (out1, out2):
            r = runner.invoke(
                app,
                [
                    "generate",
                    "--patients", "5",
                    "--seed", "7",
                    "--module", "hypertension",
                    "--out", str(path),
                ],
            )
            assert r.exit_code == 0, r.output
        # Same files, same content.
        for f1 in sorted(out1.glob("*.json")):
            f2 = out2 / f1.name
            assert f1.read_text() == f2.read_text()

"""Integration test for the bundled depression module."""

from __future__ import annotations

import json
from datetime import date

from typer.testing import CliRunner

from parker_atlas.cli import app
from parker_atlas.modules.runtime import load_module
from parker_atlas.validation.cohort import evaluate_cohort
from parker_atlas.validation.expectations import load_bundled_expectation

runner = CliRunner()

MDD_SNOMED = "370143000"
LOINC_PHQ9 = "44261-6"
RXNORM_SERTRALINE = "313700"


def _generate(tmp_path, patients=2000, seed=42):
    r = runner.invoke(
        app,
        [
            "generate",
            "--patients", str(patients),
            "--seed", str(seed),
            "--module", "depression",
            "--out", str(tmp_path),
        ],
    )
    assert r.exit_code == 0, r.output


class TestDepressionModule:
    def test_module_and_expectation_load_cleanly(self):
        load_module("depression")
        exp = load_bundled_expectation("depression")
        assert exp.module == "depression"

    def test_some_patients_get_depression(self, tmp_path):
        _generate(tmp_path, patients=5000, seed=42)
        mdd_count = 0
        for f in sorted(tmp_path.glob("*.json")):
            data = json.loads(f.read_text())
            for entry in data["entry"]:
                r = entry["resource"]
                if r["resourceType"] != "Condition":
                    continue
                for c in r["code"]["coding"]:
                    if c["code"] == MDD_SNOMED:
                        mdd_count += 1
        assert mdd_count > 0

    def test_depression_diagnosis_carries_phq9(self, tmp_path):
        _generate(tmp_path, patients=5000, seed=42)
        for f in sorted(tmp_path.glob("*.json")):
            data = json.loads(f.read_text())
            has_mdd = False
            has_phq9 = False
            for e in data["entry"]:
                r = e["resource"]
                if r["resourceType"] == "Condition":
                    for c in r["code"]["coding"]:
                        if c["code"] == MDD_SNOMED:
                            has_mdd = True
                if r["resourceType"] == "Observation":
                    for c in r.get("code", {}).get("coding", []):
                        if c.get("code") == LOINC_PHQ9:
                            has_phq9 = True
            if has_mdd:
                assert has_phq9, f"{f.name}: depression without PHQ-9 Observation"

    def test_phq9_in_moderate_to_severe_range(self, tmp_path):
        _generate(tmp_path, patients=2000, seed=42)
        any_obs = False
        for f in sorted(tmp_path.glob("*.json")):
            data = json.loads(f.read_text())
            for entry in data["entry"]:
                r = entry["resource"]
                if r["resourceType"] != "Observation":
                    continue
                for c in r.get("code", {}).get("coding", []):
                    if c.get("code") == LOINC_PHQ9:
                        any_obs = True
                        v = r["valueQuantity"]["value"]
                        # Module declares 10-20 (moderate to moderately-severe).
                        assert 10 <= v <= 20, f"PHQ-9 {v} outside [10, 20]"
        assert any_obs

    def test_cohort_harness_passes_at_n20000(self, tmp_path):
        _generate(tmp_path, patients=20000, seed=42)
        exp = load_bundled_expectation("depression")
        report = evaluate_cohort(
            tmp_path, exp, min_samples=100, reference_date=date(2026, 4, 25)
        )
        assert report.passed, (
            "Depression cohort fidelity failed:\n"
            + "\n".join(
                f"  {r.metric_id} {r.bracket} {r.sex}: actual={r.actual:.3f} "
                f"target={r.target:.3f} ±{r.tolerance:.3f}"
                for r in report.failing_metrics
            )
        )

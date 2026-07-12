"""Integration test for the bundled COPD module."""

from __future__ import annotations

import json
from datetime import date

from typer.testing import CliRunner

from parker_atlas.cli import app
from parker_atlas.modules.runtime import load_module
from parker_atlas.validation.cohort import evaluate_cohort
from parker_atlas.validation.expectations import load_bundled_expectation

runner = CliRunner()

COPD_SNOMED = "13645005"
LOINC_FEV1_FVC = "19926-5"
RXNORM_TIOTROPIUM = "1546430"


# Pin generation to the same reference date the assertions evaluate ages at, so
# a hard age-boundary invariant (pediatric prevalence 0) holds regardless of the
# wall-clock date the suite runs on.
AS_OF = "2026-04-25"


def _generate(tmp_path, patients=2000, seed=42):
    r = runner.invoke(
        app,
        [
            "generate",
            "--patients", str(patients),
            "--seed", str(seed),
            "--module", "copd",
            "--as-of", AS_OF,
            "--out", str(tmp_path),
        ],
    )
    assert r.exit_code == 0, r.output


class TestCOPDModuleParses:
    def test_module_loads_cleanly(self):
        module = load_module("copd")
        assert module.name == "copd"
        assert any(c.id == "copd" for c in module.conditions)

    def test_expectation_loads_cleanly(self):
        exp = load_bundled_expectation("copd")
        assert exp.module == "copd"
        # 1 sex_and_age prevalence + 1 emit_presence_rate.
        assert len(exp.metrics) == 2


class TestCOPDCohortGeneration:
    def test_generate_produces_some_copd_patients(self, tmp_path):
        _generate(tmp_path, patients=2000, seed=42)
        copd_count = 0
        for f in sorted(tmp_path.glob("GPX-SYN-*.json")):
            data = json.loads(f.read_text())
            for entry in data["entry"]:
                r = entry["resource"]
                if r["resourceType"] != "Condition":
                    continue
                for coding in r["code"]["coding"]:
                    if coding["code"] == COPD_SNOMED:
                        copd_count += 1
        assert copd_count > 0

    def test_copd_diagnosis_carries_fev1_fvc_observation(self, tmp_path):
        _generate(tmp_path, patients=2000, seed=42)
        for f in sorted(tmp_path.glob("GPX-SYN-*.json")):
            data = json.loads(f.read_text())
            has_copd = False
            has_fev1_fvc = False
            for e in data["entry"]:
                r = e["resource"]
                if r["resourceType"] == "Condition":
                    for coding in r["code"]["coding"]:
                        if coding["code"] == COPD_SNOMED:
                            has_copd = True
                if r["resourceType"] == "Observation":
                    for coding in r.get("code", {}).get("coding", []):
                        if coding.get("code") == LOINC_FEV1_FVC:
                            has_fev1_fvc = True
            if has_copd:
                assert has_fev1_fvc, (
                    f"Patient {f.name} has COPD diagnosis but no FEV1/FVC "
                    f"Observation."
                )

    def test_fev1_fvc_in_gold_diagnostic_range(self, tmp_path):
        _generate(tmp_path, patients=2000, seed=42)
        any_obs = False
        for f in sorted(tmp_path.glob("GPX-SYN-*.json")):
            data = json.loads(f.read_text())
            for entry in data["entry"]:
                r = entry["resource"]
                if r["resourceType"] != "Observation":
                    continue
                for coding in r.get("code", {}).get("coding", []):
                    if coding.get("code") == LOINC_FEV1_FVC:
                        any_obs = True
                        v = r["valueQuantity"]["value"]
                        # Module declares 0.50-0.69 (GOLD-criterion zone).
                        assert 0.50 <= v <= 0.69, (
                            f"FEV1/FVC {v} outside [0.50, 0.69]"
                        )
        assert any_obs

    def test_pediatric_patients_never_get_copd(self, tmp_path):
        # Module sets pediatric prevalence to 0; no patient with age <18
        # should have a COPD diagnosis.
        _generate(tmp_path, patients=5000, seed=42)
        for f in sorted(tmp_path.glob("GPX-SYN-*.json")):
            data = json.loads(f.read_text())
            patient_birth: date | None = None
            has_copd = False
            for entry in data["entry"]:
                r = entry["resource"]
                if r["resourceType"] == "Patient":
                    patient_birth = date.fromisoformat(r["birthDate"])
                if r["resourceType"] == "Condition":
                    for coding in r["code"]["coding"]:
                        if coding["code"] == COPD_SNOMED:
                            has_copd = True
            if has_copd and patient_birth is not None:
                age = (date(2026, 4, 25) - patient_birth).days // 365
                assert age >= 18, (
                    f"Pediatric patient {f.name} (age {age}) has COPD"
                )


class TestCOPDFidelityHarness:
    def test_cohort_harness_passes_at_n20000(self, tmp_path):
        _generate(tmp_path, patients=20000, seed=42)
        exp = load_bundled_expectation("copd")
        report = evaluate_cohort(
            tmp_path, exp, min_samples=100, reference_date=date(2026, 4, 25)
        )
        assert report.passed, (
            "COPD cohort fidelity failed:\n"
            + "\n".join(
                f"  {r.metric_id} {r.bracket} {r.sex}: actual={r.actual:.3f} "
                f"target={r.target:.3f} ±{r.tolerance:.3f}"
                for r in report.failing_metrics
            )
        )

"""Integration test for the bundled heart_failure module."""

from __future__ import annotations

import json
from datetime import date

from typer.testing import CliRunner

from parker_atlas.cli import app
from parker_atlas.modules.runtime import load_module
from parker_atlas.validation.cohort import evaluate_cohort
from parker_atlas.validation.expectations import load_bundled_expectation

runner = CliRunner()

HF_SNOMED = "84114007"
LOINC_NT_PROBNP = "33762-6"
RXNORM_METOPROLOL = "866412"


def _generate(tmp_path, patients=2000, seed=42):
    r = runner.invoke(
        app,
        [
            "generate",
            "--patients", str(patients),
            "--seed", str(seed),
            "--module", "heart_failure",
            "--out", str(tmp_path),
        ],
    )
    assert r.exit_code == 0, r.output


class TestHeartFailureModule:
    def test_module_and_expectation_load_cleanly(self):
        load_module("heart_failure")
        exp = load_bundled_expectation("heart_failure")
        assert exp.module == "heart_failure"

    def test_some_patients_get_hf(self, tmp_path):
        _generate(tmp_path, patients=5000, seed=42)
        hf_count = 0
        for f in sorted(tmp_path.glob("GPX-SYN-*.json")):
            data = json.loads(f.read_text())
            for entry in data["entry"]:
                r = entry["resource"]
                if r["resourceType"] != "Condition":
                    continue
                for coding in r["code"]["coding"]:
                    if coding["code"] == HF_SNOMED:
                        hf_count += 1
        assert hf_count > 0

    def test_hf_diagnosis_carries_nt_probnp(self, tmp_path):
        _generate(tmp_path, patients=5000, seed=42)
        for f in sorted(tmp_path.glob("GPX-SYN-*.json")):
            data = json.loads(f.read_text())
            has_hf = False
            has_bnp = False
            for e in data["entry"]:
                r = e["resource"]
                if r["resourceType"] == "Condition":
                    for c in r["code"]["coding"]:
                        if c["code"] == HF_SNOMED:
                            has_hf = True
                if r["resourceType"] == "Observation":
                    for c in r.get("code", {}).get("coding", []):
                        if c.get("code") == LOINC_NT_PROBNP:
                            has_bnp = True
            if has_hf:
                assert has_bnp, f"{f.name}: HF without NT-proBNP Observation"

    def test_pediatric_patients_never_get_hf(self, tmp_path):
        _generate(tmp_path, patients=5000, seed=42)
        for f in sorted(tmp_path.glob("GPX-SYN-*.json")):
            data = json.loads(f.read_text())
            patient_birth: date | None = None
            has_hf = False
            for entry in data["entry"]:
                r = entry["resource"]
                if r["resourceType"] == "Patient":
                    patient_birth = date.fromisoformat(r["birthDate"])
                if r["resourceType"] == "Condition":
                    for c in r["code"]["coding"]:
                        if c["code"] == HF_SNOMED:
                            has_hf = True
            if has_hf and patient_birth is not None:
                age = (date(2026, 4, 25) - patient_birth).days // 365
                assert age >= 18

    def test_cohort_harness_passes_at_n20000(self, tmp_path):
        _generate(tmp_path, patients=20000, seed=42)
        exp = load_bundled_expectation("heart_failure")
        report = evaluate_cohort(
            tmp_path, exp, min_samples=100, reference_date=date(2026, 4, 25)
        )
        assert report.passed, (
            "HF cohort fidelity failed:\n"
            + "\n".join(
                f"  {r.metric_id} {r.bracket} {r.sex}: actual={r.actual:.3f} "
                f"target={r.target:.3f} ±{r.tolerance:.3f}"
                for r in report.failing_metrics
            )
        )

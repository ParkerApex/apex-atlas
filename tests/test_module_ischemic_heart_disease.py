"""Integration test for the bundled ischemic_heart_disease module."""

from __future__ import annotations

import json
from datetime import date

from typer.testing import CliRunner

from parker_atlas.cli import app
from parker_atlas.modules.runtime import load_module
from parker_atlas.validation.cohort import evaluate_cohort
from parker_atlas.validation.expectations import load_bundled_expectation

runner = CliRunner()

IHD_SNOMED = "414545008"
LOINC_LDL_C = "13457-7"
RXNORM_ATORVASTATIN = "617311"
RXNORM_ASPIRIN = "243670"


def _generate(tmp_path, patients=2000, seed=42):
    r = runner.invoke(
        app,
        [
            "generate",
            "--patients", str(patients),
            "--seed", str(seed),
            "--module", "ischemic_heart_disease",
            "--out", str(tmp_path),
        ],
    )
    assert r.exit_code == 0, r.output


class TestIschemicHeartDiseaseModule:
    def test_module_and_expectation_load_cleanly(self):
        load_module("ischemic_heart_disease")
        exp = load_bundled_expectation("ischemic_heart_disease")
        assert exp.module == "ischemic_heart_disease"

    def test_some_patients_get_ihd(self, tmp_path):
        _generate(tmp_path, patients=5000, seed=42)
        ihd_count = 0
        for f in sorted(tmp_path.glob("*.json")):
            data = json.loads(f.read_text())
            for entry in data["entry"]:
                r = entry["resource"]
                if r["resourceType"] != "Condition":
                    continue
                for c in r["code"]["coding"]:
                    if c["code"] == IHD_SNOMED:
                        ihd_count += 1
        assert ihd_count > 0

    def test_ihd_diagnosis_carries_ldl_c(self, tmp_path):
        _generate(tmp_path, patients=5000, seed=42)
        for f in sorted(tmp_path.glob("*.json")):
            data = json.loads(f.read_text())
            has_ihd = False
            has_ldl = False
            for e in data["entry"]:
                r = e["resource"]
                if r["resourceType"] == "Condition":
                    for c in r["code"]["coding"]:
                        if c["code"] == IHD_SNOMED:
                            has_ihd = True
                if r["resourceType"] == "Observation":
                    for c in r.get("code", {}).get("coding", []):
                        if c.get("code") == LOINC_LDL_C:
                            has_ldl = True
            if has_ihd:
                assert has_ldl, f"{f.name}: IHD without LDL-C Observation"

    def test_pediatric_patients_never_get_ihd(self, tmp_path):
        _generate(tmp_path, patients=5000, seed=42)
        for f in sorted(tmp_path.glob("*.json")):
            data = json.loads(f.read_text())
            patient_birth: date | None = None
            has_ihd = False
            for entry in data["entry"]:
                r = entry["resource"]
                if r["resourceType"] == "Patient":
                    patient_birth = date.fromisoformat(r["birthDate"])
                if r["resourceType"] == "Condition":
                    for c in r["code"]["coding"]:
                        if c["code"] == IHD_SNOMED:
                            has_ihd = True
            if has_ihd and patient_birth is not None:
                age = (date(2026, 4, 25) - patient_birth).days // 365
                assert age >= 18

    def test_cohort_harness_passes_at_n20000(self, tmp_path):
        _generate(tmp_path, patients=20000, seed=42)
        exp = load_bundled_expectation("ischemic_heart_disease")
        report = evaluate_cohort(
            tmp_path, exp, min_samples=100, reference_date=date(2026, 4, 25)
        )
        assert report.passed, (
            "IHD cohort fidelity failed:\n"
            + "\n".join(
                f"  {r.metric_id} {r.bracket} {r.sex}: actual={r.actual:.3f} "
                f"target={r.target:.3f} ±{r.tolerance:.3f}"
                for r in report.failing_metrics
            )
        )

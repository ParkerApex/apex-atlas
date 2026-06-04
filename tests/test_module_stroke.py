"""Integration test for the bundled stroke module."""

from __future__ import annotations

import json
from datetime import date

from typer.testing import CliRunner

from parker_atlas.cli import app
from parker_atlas.modules.runtime import load_module
from parker_atlas.validation.cohort import evaluate_cohort
from parker_atlas.validation.expectations import load_bundled_expectation

runner = CliRunner()

STROKE_SNOMED = "230690007"
LOINC_NIHSS = "70182-1"
RXNORM_ASPIRIN = "243670"


def _generate(tmp_path, patients=2000, seed=42):
    r = runner.invoke(
        app,
        [
            "generate",
            "--patients", str(patients),
            "--seed", str(seed),
            "--module", "stroke",
            "--out", str(tmp_path),
        ],
    )
    assert r.exit_code == 0, r.output


class TestStrokeModule:
    def test_module_and_expectation_load_cleanly(self):
        load_module("stroke")
        exp = load_bundled_expectation("stroke")
        assert exp.module == "stroke"

    def test_some_patients_get_stroke(self, tmp_path):
        _generate(tmp_path, patients=5000, seed=42)
        stroke_count = 0
        for f in sorted(tmp_path.glob("GPX-SYN-*.json")):
            data = json.loads(f.read_text())
            for entry in data["entry"]:
                r = entry["resource"]
                if r["resourceType"] != "Condition":
                    continue
                for c in r["code"]["coding"]:
                    if c["code"] == STROKE_SNOMED:
                        stroke_count += 1
        assert stroke_count > 0

    def test_stroke_diagnosis_carries_nihss(self, tmp_path):
        _generate(tmp_path, patients=5000, seed=42)
        for f in sorted(tmp_path.glob("GPX-SYN-*.json")):
            data = json.loads(f.read_text())
            has_stroke = False
            has_nihss = False
            for e in data["entry"]:
                r = e["resource"]
                if r["resourceType"] == "Condition":
                    for c in r["code"]["coding"]:
                        if c["code"] == STROKE_SNOMED:
                            has_stroke = True
                if r["resourceType"] == "Observation":
                    for c in r.get("code", {}).get("coding", []):
                        if c.get("code") == LOINC_NIHSS:
                            has_nihss = True
            if has_stroke:
                assert has_nihss, f"{f.name}: stroke without NIHSS Observation"

    def test_pediatric_patients_never_get_stroke(self, tmp_path):
        _generate(tmp_path, patients=5000, seed=42)
        for f in sorted(tmp_path.glob("GPX-SYN-*.json")):
            data = json.loads(f.read_text())
            patient_birth: date | None = None
            has_stroke = False
            for entry in data["entry"]:
                r = entry["resource"]
                if r["resourceType"] == "Patient":
                    patient_birth = date.fromisoformat(r["birthDate"])
                if r["resourceType"] == "Condition":
                    for c in r["code"]["coding"]:
                        if c["code"] == STROKE_SNOMED:
                            has_stroke = True
            if has_stroke and patient_birth is not None:
                age = (date(2026, 4, 25) - patient_birth).days // 365
                assert age >= 18

    def test_cohort_harness_passes_at_n20000(self, tmp_path):
        _generate(tmp_path, patients=20000, seed=42)
        exp = load_bundled_expectation("stroke")
        report = evaluate_cohort(
            tmp_path, exp, min_samples=100, reference_date=date(2026, 4, 25)
        )
        assert report.passed, (
            "Stroke cohort fidelity failed:\n"
            + "\n".join(
                f"  {r.metric_id} {r.bracket} {r.sex}: actual={r.actual:.3f} "
                f"target={r.target:.3f} ±{r.tolerance:.3f}"
                for r in report.failing_metrics
            )
        )

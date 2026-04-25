"""Integration test for DM → diabetic_retinopathy progression in the
bundled diabetes module.

End-to-end against the real YAML so authoring changes to diabetes.yaml
are caught here. Mirrors the test_module_diabetes_ckd.py pattern, with
ophthalmology-flavored emits instead of nephrology.
"""

from __future__ import annotations

import json
from datetime import date

from typer.testing import CliRunner

from parker_atlas.cli import app

runner = CliRunner()


DM_SNOMED = "73211009"
DR_SNOMED = "4855003"
LOINC_VISUAL_ACUITY = "70936-0"


def _generate(tmp_path, patients=2000, seed=42):
    r = runner.invoke(
        app,
        [
            "generate",
            "--patients", str(patients),
            "--seed", str(seed),
            "--module", "diabetes",
            "--out", str(tmp_path),
        ],
    )
    assert r.exit_code == 0, r.output


def _walk_conditions(tmp_path):
    for f in sorted(tmp_path.glob("*.json")):
        data = json.loads(f.read_text())
        gpx = f.stem
        for entry in data["entry"]:
            r = entry["resource"]
            if r["resourceType"] == "Condition":
                yield gpx, r


class TestDiabeticRetinopathyProgression:
    def test_some_patients_progress_to_retinopathy(self, tmp_path):
        _generate(tmp_path, patients=2000, seed=42)
        dm = dr = 0
        for _, cond in _walk_conditions(tmp_path):
            for coding in cond["code"]["coding"]:
                if coding["code"] == DM_SNOMED:
                    dm += 1
                elif coding["code"] == DR_SNOMED:
                    dr += 1
        assert dm > 0
        assert dr > 0

    def test_retinopathy_only_in_patients_with_diabetes(self, tmp_path):
        _generate(tmp_path, patients=2000, seed=42)
        by_patient: dict[str, set[str]] = {}
        for gpx, cond in _walk_conditions(tmp_path):
            codes = by_patient.setdefault(gpx, set())
            for coding in cond["code"]["coding"]:
                codes.add(coding["code"])
        for gpx, codes in by_patient.items():
            if DR_SNOMED in codes:
                assert DM_SNOMED in codes, (
                    f"patient {gpx} has DR but not diabetes — progression-only "
                    f"target leaked"
                )

    def test_progression_rate_in_ballpark(self, tmp_path):
        _generate(tmp_path, patients=5000, seed=42)
        dm_p: set[str] = set()
        dr_p: set[str] = set()
        for gpx, cond in _walk_conditions(tmp_path):
            for coding in cond["code"]["coding"]:
                if coding["code"] == DM_SNOMED:
                    dm_p.add(gpx)
                elif coding["code"] == DR_SNOMED:
                    dr_p.add(gpx)
        rate = len(dr_p) / max(len(dm_p), 1)
        # Sourced 30% over 10 yr; cohort rate ≈ 20% empirically.
        assert 0.10 < rate < 0.30, (
            f"DM→DR progression rate {rate:.3f} outside the expected "
            f"0.10-0.30 sanity band (DM={len(dm_p)}, DR={len(dr_p)})"
        )

    def test_dr_diagnosis_carries_visual_acuity_observation(self, tmp_path):
        _generate(tmp_path, patients=2000, seed=42)
        for f in sorted(tmp_path.glob("*.json")):
            data = json.loads(f.read_text())
            has_dr = False
            has_va = False
            for e in data["entry"]:
                r = e["resource"]
                if r["resourceType"] == "Condition":
                    for coding in r["code"]["coding"]:
                        if coding["code"] == DR_SNOMED:
                            has_dr = True
                if r["resourceType"] == "Observation":
                    for coding in r.get("code", {}).get("coding", []):
                        if coding.get("code") == LOINC_VISUAL_ACUITY:
                            has_va = True
            if has_dr:
                assert has_va, (
                    f"Patient {f.name} has DR diagnosis but no visual-acuity "
                    f"Observation."
                )

    def test_dr_onset_is_ten_years_after_diabetes_onset(self, tmp_path):
        _generate(tmp_path, patients=2000, seed=42)
        for f in sorted(tmp_path.glob("*.json")):
            data = json.loads(f.read_text())
            dm_onset: date | None = None
            dr_onset: date | None = None
            for entry in data["entry"]:
                r = entry["resource"]
                if r["resourceType"] != "Condition":
                    continue
                onset = r.get("onsetDateTime")
                if not onset:
                    continue
                onset_date = date.fromisoformat(onset[:10])
                for coding in r["code"]["coding"]:
                    if coding["code"] == DM_SNOMED:
                        dm_onset = onset_date
                    elif coding["code"] == DR_SNOMED:
                        dr_onset = onset_date
            if dm_onset is not None and dr_onset is not None:
                delta_days = (dr_onset - dm_onset).days
                assert delta_days == 10 * 365, (
                    f"Patient {f.name}: DR onset is {delta_days} days "
                    f"after diabetes onset; expected exactly {10 * 365}."
                )

    def test_visual_acuity_in_logmar_npdr_range(self, tmp_path):
        _generate(tmp_path, patients=2000, seed=42)
        any_va = False
        for f in sorted(tmp_path.glob("*.json")):
            data = json.loads(f.read_text())
            for entry in data["entry"]:
                r = entry["resource"]
                if r["resourceType"] != "Observation":
                    continue
                for coding in r.get("code", {}).get("coding", []):
                    if coding.get("code") == LOINC_VISUAL_ACUITY:
                        any_va = True
                        v = r["valueQuantity"]["value"]
                        # Module declares range 0.0-0.3 LogMAR (mild-moderate
                        # NPDR); allow the full inclusive interval.
                        assert 0.0 <= v <= 0.3, f"LogMAR {v} outside [0.0, 0.3]"
        assert any_va, "expected at least one visual-acuity Observation"

    def test_overlay_drives_both_progressions(self, tmp_path):
        # Sanity check: the bundled diabetes overlay declares two
        # progressions, and both fire in cohort.
        _generate(tmp_path, patients=2000, seed=42)
        ckd = dr = 0
        for _, cond in _walk_conditions(tmp_path):
            for coding in cond["code"]["coding"]:
                if coding["code"] == "420715001":
                    ckd += 1
                elif coding["code"] == DR_SNOMED:
                    dr += 1
        assert ckd > 0
        assert dr > 0

"""Integration test for the DM → diabetic_ckd progression in the
bundled diabetes module.

End-to-end against the real YAML so authoring changes to diabetes.yaml
are caught here.
"""

from __future__ import annotations

import json
from datetime import date

from typer.testing import CliRunner

from parker_atlas.cli import app

runner = CliRunner()


DM_SNOMED = "73211009"
DM_CKD_SNOMED = "420715001"


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


class TestDiabeticCKDProgression:
    def test_some_patients_progress_to_ckd(self, tmp_path):
        _generate(tmp_path, patients=2000, seed=42)
        dm = ckd = 0
        for _, cond in _walk_conditions(tmp_path):
            for coding in cond["code"]["coding"]:
                if coding["code"] == DM_SNOMED:
                    dm += 1
                elif coding["code"] == DM_CKD_SNOMED:
                    ckd += 1
        assert dm > 0
        assert ckd > 0

    def test_ckd_only_in_patients_with_diabetes(self, tmp_path):
        _generate(tmp_path, patients=2000, seed=42)
        by_patient: dict[str, set[str]] = {}
        for gpx, cond in _walk_conditions(tmp_path):
            codes = by_patient.setdefault(gpx, set())
            for coding in cond["code"]["coding"]:
                codes.add(coding["code"])
        for gpx, codes in by_patient.items():
            if DM_CKD_SNOMED in codes:
                assert DM_SNOMED in codes, (
                    f"patient {gpx} has diabetic CKD but not diabetes — "
                    f"progression-only target leaked"
                )

    def test_progression_rate_in_ballpark(self, tmp_path):
        _generate(tmp_path, patients=5000, seed=42)
        dm_patients: set[str] = set()
        ckd_patients: set[str] = set()
        for gpx, cond in _walk_conditions(tmp_path):
            for coding in cond["code"]["coding"]:
                if coding["code"] == DM_SNOMED:
                    dm_patients.add(gpx)
                elif coding["code"] == DM_CKD_SNOMED:
                    ckd_patients.add(gpx)
        rate = len(ckd_patients) / max(len(dm_patients), 1)
        # DM2 onset_age 35-70 + 10y delay; cohort rate ≈ 12% empirically.
        assert 0.05 < rate < 0.20, (
            f"DM→CKD progression rate {rate:.3f} outside the expected "
            f"0.05-0.20 sanity band (DM={len(dm_patients)}, "
            f"CKD={len(ckd_patients)})"
        )

    def test_ckd_diagnosis_carries_egfr_observation(self, tmp_path):
        _generate(tmp_path, patients=2000, seed=42)
        for f in sorted(tmp_path.glob("*.json")):
            data = json.loads(f.read_text())
            has_ckd = False
            has_egfr = False
            for e in data["entry"]:
                r = e["resource"]
                if r["resourceType"] == "Condition":
                    for coding in r["code"]["coding"]:
                        if coding["code"] == DM_CKD_SNOMED:
                            has_ckd = True
                if r["resourceType"] == "Observation":
                    for coding in r.get("code", {}).get("coding", []):
                        if coding.get("code") == "33914-3":
                            has_egfr = True
            if has_ckd:
                assert has_egfr, (
                    f"Patient {f.name} has diabetic CKD diagnosis but no "
                    f"eGFR Observation."
                )

    def test_ckd_onset_is_ten_years_after_diabetes_onset(self, tmp_path):
        _generate(tmp_path, patients=2000, seed=42)
        for f in sorted(tmp_path.glob("*.json")):
            data = json.loads(f.read_text())
            dm_onset: date | None = None
            ckd_onset: date | None = None
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
                    elif coding["code"] == DM_CKD_SNOMED:
                        ckd_onset = onset_date
            if dm_onset is not None and ckd_onset is not None:
                delta_days = (ckd_onset - dm_onset).days
                assert delta_days == 10 * 365, (
                    f"Patient {f.name}: diabetic CKD onset is {delta_days} "
                    f"days after diabetes onset; expected exactly {10 * 365}."
                )

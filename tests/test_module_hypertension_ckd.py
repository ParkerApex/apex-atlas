"""Integration test for the HTN → hypertensive_ckd progression in the
bundled hypertension module.

This is end-to-end against the real YAML, not a synthetic fixture, so
that authoring changes to hypertension.yaml are caught here.
"""

from __future__ import annotations

import json

from typer.testing import CliRunner

from parker_atlas.cli import app

runner = CliRunner()


CKD_SNOMED = "709044004"
HTN_SNOMED = "59621000"


def _generate(tmp_path, patients=2000, seed=42):
    r = runner.invoke(
        app,
        [
            "generate",
            "--patients", str(patients),
            "--seed", str(seed),
            "--module", "hypertension",
            "--out", str(tmp_path),
        ],
    )
    assert r.exit_code == 0, r.output


def _walk_conditions(tmp_path):
    """Yield (gpx, condition_dict) for every Condition across every Bundle."""
    for f in sorted(tmp_path.glob("GPX-SYN-*.json")):
        data = json.loads(f.read_text())
        gpx = f.stem
        for entry in data["entry"]:
            r = entry["resource"]
            if r["resourceType"] == "Condition":
                yield gpx, r


class TestHypertensiveCKDProgression:
    def test_some_patients_progress_to_ckd(self, tmp_path):
        _generate(tmp_path, patients=2000, seed=42)
        ckd_count = 0
        htn_count = 0
        for _, cond in _walk_conditions(tmp_path):
            for coding in cond["code"]["coding"]:
                if coding["code"] == CKD_SNOMED:
                    ckd_count += 1
                elif coding["code"] == HTN_SNOMED:
                    htn_count += 1
        assert htn_count > 0, "expected HTN to fire"
        assert ckd_count > 0, "expected at least one HTN→CKD progression"

    def test_ckd_only_in_patients_with_htn(self, tmp_path):
        _generate(tmp_path, patients=2000, seed=42)
        # CKD here is progression-only — no patient should have CKD without HTN.
        by_patient: dict[str, set[str]] = {}
        for gpx, cond in _walk_conditions(tmp_path):
            codes = by_patient.setdefault(gpx, set())
            for coding in cond["code"]["coding"]:
                codes.add(coding["code"])
        for gpx, codes in by_patient.items():
            if CKD_SNOMED in codes:
                assert HTN_SNOMED in codes, (
                    f"patient {gpx} has CKD but not HTN — progression-only "
                    f"target leaked"
                )

    def test_ckd_progression_rate_in_ballpark(self, tmp_path):
        # Probability is 0.10 over 10 years. Among HTN-positive patients
        # with onset >10 years ago, ~10% should fire CKD. The exact cohort
        # rate depends on age × onset_age × current age, but at N=5000
        # we expect *some* fraction in a wide ballpark.
        _generate(tmp_path, patients=5000, seed=42)
        htn_patients: set[str] = set()
        ckd_patients: set[str] = set()
        for gpx, cond in _walk_conditions(tmp_path):
            for coding in cond["code"]["coding"]:
                if coding["code"] == HTN_SNOMED:
                    htn_patients.add(gpx)
                elif coding["code"] == CKD_SNOMED:
                    ckd_patients.add(gpx)
        # Proportion of HTN patients who also have CKD. Sanity range only:
        # the population includes patients whose HTN onset is <10yr ago who
        # cannot progress. A handful of percent is the realistic floor.
        rate = len(ckd_patients) / max(len(htn_patients), 1)
        assert 0.005 < rate < 0.15, (
            f"HTN→CKD progression rate {rate:.3f} outside the expected "
            f"0.005-0.15 sanity band (HTN={len(htn_patients)}, "
            f"CKD={len(ckd_patients)})"
        )

    def test_ckd_diagnosis_carries_egfr_observation(self, tmp_path):
        _generate(tmp_path, patients=2000, seed=42)
        # For each patient with a CKD diagnosis, confirm an eGFR Observation
        # was emitted.
        for f in sorted(tmp_path.glob("GPX-SYN-*.json")):
            data = json.loads(f.read_text())
            entries = data["entry"]
            has_ckd = False
            has_egfr = False
            for e in entries:
                r = e["resource"]
                if r["resourceType"] == "Condition":
                    for coding in r["code"]["coding"]:
                        if coding["code"] == CKD_SNOMED:
                            has_ckd = True
                if r["resourceType"] == "Observation":
                    for coding in r.get("code", {}).get("coding", []):
                        if coding.get("code") == "33914-3":
                            has_egfr = True
            if has_ckd:
                assert has_egfr, (
                    f"Patient {f.name} has CKD diagnosis but no eGFR "
                    f"Observation — progression emit missing."
                )

    def test_ckd_onset_predates_progression_offset(self, tmp_path):
        from datetime import date

        _generate(tmp_path, patients=2000, seed=42)
        # A patient's CKD onset must be exactly 10 years (3650 days) after
        # their HTN onset.
        for f in sorted(tmp_path.glob("GPX-SYN-*.json")):
            data = json.loads(f.read_text())
            htn_onset: date | None = None
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
                    if coding["code"] == HTN_SNOMED:
                        htn_onset = onset_date
                    elif coding["code"] == CKD_SNOMED:
                        ckd_onset = onset_date
            if htn_onset is not None and ckd_onset is not None:
                delta_days = (ckd_onset - htn_onset).days
                assert delta_days == 10 * 365, (
                    f"Patient {f.name}: CKD onset is {delta_days} days "
                    f"after HTN onset; expected exactly {10 * 365}."
                )

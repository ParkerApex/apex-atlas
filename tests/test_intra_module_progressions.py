"""Integration tests for the intra-module progression chains added in
the cross-module-progressions batch:

- ischemic_heart_disease → myocardial_infarction
- heart_failure → cardiorenal_syndrome
"""

from __future__ import annotations

import json
from datetime import date

from typer.testing import CliRunner

from parker_atlas.cli import app

runner = CliRunner()


IHD_SNOMED = "414545008"
MI_SNOMED = "22298006"
HF_SNOMED = "84114007"
CARDIORENAL_SNOMED = "707577004"


def _generate(tmp_path, *, modules: str, patients: int = 5000, seed: int = 42):
    r = runner.invoke(
        app,
        [
            "generate",
            "--patients", str(patients),
            "--seed", str(seed),
            "--module", modules,
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


class TestIHDToMIChain:
    def test_some_ihd_patients_progress_to_mi(self, tmp_path):
        _generate(tmp_path, modules="ischemic_heart_disease", patients=5000)
        ihd_patients: set[str] = set()
        mi_patients: set[str] = set()
        for gpx, cond in _walk_conditions(tmp_path):
            for c in cond["code"]["coding"]:
                if c["code"] == IHD_SNOMED:
                    ihd_patients.add(gpx)
                elif c["code"] == MI_SNOMED:
                    mi_patients.add(gpx)
        assert len(ihd_patients) > 0
        assert len(mi_patients) > 0

    def test_mi_only_in_patients_with_ihd(self, tmp_path):
        _generate(tmp_path, modules="ischemic_heart_disease", patients=5000)
        by_patient: dict[str, set[str]] = {}
        for gpx, cond in _walk_conditions(tmp_path):
            codes = by_patient.setdefault(gpx, set())
            for c in cond["code"]["coding"]:
                codes.add(c["code"])
        for gpx, codes in by_patient.items():
            if MI_SNOMED in codes:
                assert IHD_SNOMED in codes, (
                    f"patient {gpx} has MI without IHD — progression-only "
                    f"target leaked"
                )

    def test_mi_diagnosis_carries_inpatient_encounter(self, tmp_path):
        _generate(tmp_path, modules="ischemic_heart_disease", patients=5000)
        for f in sorted(tmp_path.glob("*.json")):
            data = json.loads(f.read_text())
            has_mi = False
            inpatient_encounters = []
            for e in data["entry"]:
                r = e["resource"]
                if r["resourceType"] == "Condition":
                    for c in r["code"]["coding"]:
                        if c["code"] == MI_SNOMED:
                            has_mi = True
                if r["resourceType"] == "Encounter":
                    if r.get("class", {}).get("code") == "IMP":
                        inpatient_encounters.append(r)
            if has_mi:
                assert inpatient_encounters, (
                    f"{f.name}: MI without inpatient Encounter"
                )

    def test_mi_onset_is_ten_years_after_ihd_onset(self, tmp_path):
        _generate(tmp_path, modules="ischemic_heart_disease", patients=2000)
        for f in sorted(tmp_path.glob("*.json")):
            data = json.loads(f.read_text())
            ihd_onset: date | None = None
            mi_onset: date | None = None
            for entry in data["entry"]:
                r = entry["resource"]
                if r["resourceType"] != "Condition":
                    continue
                onset = r.get("onsetDateTime")
                if not onset:
                    continue
                onset_date = date.fromisoformat(onset[:10])
                for c in r["code"]["coding"]:
                    if c["code"] == IHD_SNOMED:
                        ihd_onset = onset_date
                    elif c["code"] == MI_SNOMED:
                        mi_onset = onset_date
            if ihd_onset is not None and mi_onset is not None:
                assert (mi_onset - ihd_onset).days == 10 * 365


class TestHFToCardiorenalChain:
    def test_some_hf_patients_progress_to_cardiorenal(self, tmp_path):
        _generate(tmp_path, modules="heart_failure", patients=5000)
        hf_patients: set[str] = set()
        crs_patients: set[str] = set()
        for gpx, cond in _walk_conditions(tmp_path):
            for c in cond["code"]["coding"]:
                if c["code"] == HF_SNOMED:
                    hf_patients.add(gpx)
                elif c["code"] == CARDIORENAL_SNOMED:
                    crs_patients.add(gpx)
        assert len(hf_patients) > 0
        assert len(crs_patients) > 0

    def test_cardiorenal_only_in_patients_with_hf(self, tmp_path):
        _generate(tmp_path, modules="heart_failure", patients=5000)
        by_patient: dict[str, set[str]] = {}
        for gpx, cond in _walk_conditions(tmp_path):
            codes = by_patient.setdefault(gpx, set())
            for c in cond["code"]["coding"]:
                codes.add(c["code"])
        for gpx, codes in by_patient.items():
            if CARDIORENAL_SNOMED in codes:
                assert HF_SNOMED in codes

    def test_cardiorenal_diagnosis_carries_egfr(self, tmp_path):
        _generate(tmp_path, modules="heart_failure", patients=5000)
        for f in sorted(tmp_path.glob("*.json")):
            data = json.loads(f.read_text())
            has_crs = False
            has_egfr = False
            for e in data["entry"]:
                r = e["resource"]
                if r["resourceType"] == "Condition":
                    for c in r["code"]["coding"]:
                        if c["code"] == CARDIORENAL_SNOMED:
                            has_crs = True
                if r["resourceType"] == "Observation":
                    for c in r.get("code", {}).get("coding", []):
                        if c.get("code") == "33914-3":
                            has_egfr = True
            if has_crs:
                assert has_egfr, f"{f.name}: cardiorenal without eGFR"

    def test_cardiorenal_onset_is_ten_years_after_hf_onset(self, tmp_path):
        _generate(tmp_path, modules="heart_failure", patients=2000)
        for f in sorted(tmp_path.glob("*.json")):
            data = json.loads(f.read_text())
            hf_onset: date | None = None
            crs_onset: date | None = None
            for entry in data["entry"]:
                r = entry["resource"]
                if r["resourceType"] != "Condition":
                    continue
                onset = r.get("onsetDateTime")
                if not onset:
                    continue
                onset_date = date.fromisoformat(onset[:10])
                for c in r["code"]["coding"]:
                    if c["code"] == HF_SNOMED:
                        hf_onset = onset_date
                    elif c["code"] == CARDIORENAL_SNOMED:
                        crs_onset = onset_date
            if hf_onset is not None and crs_onset is not None:
                assert (crs_onset - hf_onset).days == 10 * 365

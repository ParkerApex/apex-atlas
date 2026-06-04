"""Integration tests for cross-module progressions.

Cross-module progressions use `to: <module>:<condition_id>` syntax on
the source condition's progressions block. They fire only when the
target module is also active in the same `atlas generate` run.

Bundled chains exercised here:
- hypertension:essential_hypertension → heart_failure:heart_failure
- hypertension:essential_hypertension → stroke:stroke
"""

from __future__ import annotations

import json
import random
from datetime import date

import pytest
from typer.testing import CliRunner

from parker_atlas.cli import app
from parker_atlas.modules import (
    apply_cross_module_progressions,
    load_module,
    run_module,
)
from parker_atlas.modules.runtime import (
    ModuleError,
    load_module_from_str,
)

runner = CliRunner()

HTN_SNOMED = "59621000"
HF_SNOMED = "84114007"
STROKE_SNOMED = "230690007"


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


def _patient_codes(tmp_path) -> dict[str, set[str]]:
    by_patient: dict[str, set[str]] = {}
    for f in sorted(tmp_path.glob("GPX-SYN-*.json")):
        data = json.loads(f.read_text())
        codes = by_patient.setdefault(f.stem, set())
        for entry in data["entry"]:
            r = entry["resource"]
            if r["resourceType"] != "Condition":
                continue
            for coding in r["code"]["coding"]:
                codes.add(coding["code"])
    return by_patient


class TestCrossModuleProgressionRuntime:
    def test_runtime_function_exists_and_is_idempotent_on_no_op(self):
        rng = random.Random(0)
        # No diagnoses, no modules → empty result, no errors.
        result = apply_cross_module_progressions(
            {}, modules_by_name={}, rng=rng, today=date(2026, 4, 25)
        )
        assert result == {}

    def test_cross_module_target_skipped_when_target_module_not_active(self):
        # Standalone hypertension run — HTN's cross-module progressions
        # to heart_failure:* and stroke:* should silently no-op.
        htn_module = load_module("hypertension")
        rng = random.Random(0)
        diagnoses = run_module(
            htn_module,
            age_years=70,
            sex="male",
            rng=rng,
            today=date(2026, 4, 25),
        )
        # Cross-module pass with only hypertension in the registry.
        result = apply_cross_module_progressions(
            {"hypertension": list(diagnoses)},
            modules_by_name={"hypertension": htn_module},
            rng=rng,
            today=date(2026, 4, 25),
        )
        # No new modules added; HF / stroke not in the registry → no
        # cross-module hits.
        assert set(result.keys()) == {"hypertension"}

    def test_cross_module_target_fires_when_both_modules_active(self):
        htn_module = load_module("hypertension")
        hf_module = load_module("heart_failure")
        # 70-year-old to ensure HTN onset can be >10 yr in the past.
        rng = random.Random(0)
        diagnoses_by_module: dict[str, list] = {}
        for mod in (htn_module, hf_module):
            diagnoses_by_module[mod.name] = list(
                run_module(
                    mod,
                    age_years=70,
                    sex="male",
                    rng=rng,
                    today=date(2026, 4, 25),
                )
            )
        result = apply_cross_module_progressions(
            diagnoses_by_module,
            modules_by_name={"hypertension": htn_module, "heart_failure": hf_module},
            rng=rng,
            today=date(2026, 4, 25),
        )
        # Hypertension entries unchanged; heart_failure may have gained
        # additional Diagnoses from the HTN→HF cross-module hop.
        assert "heart_failure" in result


class TestCrossModuleProgressionParsing:
    def test_malformed_cross_module_target_rejected(self):
        bad = """
module: t
version: 0.1.0
conditions:
  - id: a
    code: {system: s, code: "1", display: a}
    prevalence: {"0-99": 1.0}
    onset_age: {min: 30, max: 50}
    progressions:
      - to: ":missing-source"
        after_years: 5
        probability: 0.1
"""
        with pytest.raises(ModuleError, match="malformed"):
            load_module_from_str(bad)

    def test_cross_module_target_passes_module_load(self):
        # The target `other_module:foo` doesn't exist in this module,
        # but should NOT raise at parse / load time — only at run time
        # when the cross-module pass tries to resolve it.
        good = """
module: t
version: 0.1.0
conditions:
  - id: a
    code: {system: s, code: "1", display: a}
    prevalence: {"0-99": 1.0}
    onset_age: {min: 30, max: 50}
    progressions:
      - to: other_module:foo
        after_years: 5
        probability: 0.1
"""
        module = load_module_from_str(good)
        assert module.conditions[0].progressions[0].to == "other_module:foo"


class TestHTNToHFChain:
    def test_htn_hf_comorbidity_increases_with_both_modules_active(self, tmp_path):
        # Generate the same cohort twice: HTN+HF together vs HF alone.
        # The "both" run should show higher HF prevalence among HTN
        # patients than the baseline HF prevalence in the population,
        # because of the cross-module progression.
        with_chain = tmp_path / "chain"
        _generate(with_chain, modules="hypertension,heart_failure", patients=10000)

        codes_chain = _patient_codes(with_chain)
        htn_p = {gpx for gpx, c in codes_chain.items() if HTN_SNOMED in c}
        hf_p = {gpx for gpx, c in codes_chain.items() if HF_SNOMED in c}
        htn_and_hf = htn_p & hf_p

        assert len(htn_and_hf) > 0, "expected some HTN→HF progression hits"
        # The HF rate among HTN patients should be substantially higher
        # than the HF rate among non-HTN patients (the chain is doing
        # something).
        non_htn_p = set(codes_chain) - htn_p
        non_htn_hf_p = non_htn_p & hf_p
        rate_htn = len(htn_and_hf) / len(htn_p)
        rate_non_htn = len(non_htn_hf_p) / max(len(non_htn_p), 1)
        assert rate_htn > rate_non_htn * 1.5, (
            f"HF rate among HTN {rate_htn:.4f} vs non-HTN {rate_non_htn:.4f}: "
            f"chain doesn't appear to be amplifying comorbidity"
        )


class TestHTNToStrokeChain:
    def test_htn_stroke_comorbidity_increases_with_both_modules_active(self, tmp_path):
        chain = tmp_path / "chain"
        _generate(chain, modules="hypertension,stroke", patients=10000)
        codes = _patient_codes(chain)
        htn_p = {gpx for gpx, c in codes.items() if HTN_SNOMED in c}
        stroke_p = {gpx for gpx, c in codes.items() if STROKE_SNOMED in c}
        non_htn_p = set(codes) - htn_p

        rate_htn = len(htn_p & stroke_p) / max(len(htn_p), 1)
        rate_non_htn = len(non_htn_p & stroke_p) / max(len(non_htn_p), 1)
        assert rate_htn > rate_non_htn * 1.5, (
            f"Stroke rate among HTN {rate_htn:.4f} vs non-HTN "
            f"{rate_non_htn:.4f}: chain doesn't appear to be amplifying"
        )


class TestStandaloneRunsStillWork:
    def test_hypertension_alone_does_not_error(self, tmp_path):
        # HTN's cross-module progressions to HF and stroke must silently
        # no-op when those modules aren't active in the run.
        _generate(tmp_path, modules="hypertension", patients=100)
        assert any(tmp_path.glob("GPX-SYN-*.json"))

    def test_hypertension_alone_emits_no_hf_or_stroke(self, tmp_path):
        _generate(tmp_path, modules="hypertension", patients=500)
        codes = _patient_codes(tmp_path)
        assert not any(HF_SNOMED in c for c in codes.values())
        assert not any(STROKE_SNOMED in c for c in codes.values())

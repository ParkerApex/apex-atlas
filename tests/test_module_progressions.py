"""Tests for the minimal state-machine progressions feature.

A condition can declare `progressions: [{to, after_years, probability}]`.
After all conditions have fired via their normal prevalence trial, the
runtime evaluates each fired condition's progressions: if enough time
has elapsed since the source's onset_date, a Bernoulli(probability)
trial decides whether the target condition also fires (with onset_date
set to source.onset_date + after_years).
"""

from __future__ import annotations

import random
from datetime import date

import pytest

from parker_atlas.modules.runtime import (
    ModuleError,
    ProgressionSpec,
    load_module_from_str,
    run_module,
)


_BASE_HTN_BLOCK = """
module: htn_progression_test
version: 0.1.0
description: Minimal module exercising progression semantics.
conditions:
  - id: essential_hypertension
    code: {system: http://snomed.info/sct, code: "59621000", display: HTN}
    prevalence:
      "0-99": 1.0
    onset_age: {min: 30, max: 50}
    progressions:
      - to: hypertensive_ckd
        after_years: 5
        probability: 1.0
  - id: hypertensive_ckd
    code: {system: http://snomed.info/sct, code: "709044004", display: CKD due to HTN}
    prevalence:
      "0-99": 0.0
"""


class TestProgressionParsing:
    def test_parses_progressions_block(self):
        mod = load_module_from_str(_BASE_HTN_BLOCK)
        htn = mod.conditions[0]
        assert len(htn.progressions) == 1
        assert htn.progressions[0] == ProgressionSpec(
            to="hypertensive_ckd", after_years=5, probability=1.0
        )

    def test_progression_target_must_exist(self):
        bad = _BASE_HTN_BLOCK.replace("hypertensive_ckd", "ghost_condition", 1)
        # Only replace the `to:` reference, not the actual condition declaration.
        # The above replace replaced both — restore the second.
        bad = bad.replace(
            "  - id: ghost_condition", "  - id: hypertensive_ckd"
        )
        # Now `to: ghost_condition` references a non-existent sibling.
        with pytest.raises(ModuleError, match="must reference a sibling condition"):
            load_module_from_str(bad)

    def test_progression_to_self_rejected(self):
        bad = """
module: t
version: 0.1.0
conditions:
  - id: c
    code: {system: s, code: "1", display: c}
    prevalence: {"0-99": 1.0}
    onset_age: {min: 30, max: 50}
    progressions:
      - to: c
        after_years: 5
        probability: 0.5
"""
        with pytest.raises(ModuleError, match="cannot.*reference itself"):
            load_module_from_str(bad)

    def test_progression_requires_onset_age(self):
        bad = """
module: t
version: 0.1.0
conditions:
  - id: a
    code: {system: s, code: "1", display: a}
    prevalence: {"0-99": 1.0}
    progressions:
      - to: b
        after_years: 5
        probability: 0.5
  - id: b
    code: {system: s, code: "2", display: b}
    prevalence: {"0-99": 0.0}
"""
        with pytest.raises(ModuleError, match="onset_age"):
            load_module_from_str(bad)

    def test_invalid_probability_rejected(self):
        bad = _BASE_HTN_BLOCK.replace("probability: 1.0", "probability: 1.5")
        with pytest.raises(ModuleError, match="probability"):
            load_module_from_str(bad)

    def test_negative_after_years_rejected(self):
        bad = _BASE_HTN_BLOCK.replace("after_years: 5", "after_years: -1")
        with pytest.raises(ModuleError, match="after_years"):
            load_module_from_str(bad)

    def test_duplicate_progression_targets_rejected(self):
        bad = """
module: t
version: 0.1.0
conditions:
  - id: a
    code: {system: s, code: "1", display: a}
    prevalence: {"0-99": 1.0}
    onset_age: {min: 30, max: 50}
    progressions:
      - to: b
        after_years: 5
        probability: 0.5
      - to: b
        after_years: 10
        probability: 0.3
  - id: b
    code: {system: s, code: "2", display: b}
    prevalence: {"0-99": 0.0}
"""
        with pytest.raises(ModuleError, match="duplicate progression"):
            load_module_from_str(bad)


class TestProgressionRuntime:
    def test_progression_fires_when_enough_time_elapsed(self):
        mod = load_module_from_str(_BASE_HTN_BLOCK)
        rng = random.Random(0)
        # 60-year-old; HTN onset sampled from age 30-50 → onset 10-30 years ago.
        # Progression fires after 5 years → always satisfied.
        # Both prevalence and progression probability are 1.0.
        diagnoses = run_module(
            mod, age_years=60, sex="female", rng=rng, today=date(2026, 1, 1)
        )
        ids = [dx.condition.id for dx in diagnoses]
        assert "essential_hypertension" in ids
        assert "hypertensive_ckd" in ids

    def test_progression_skipped_when_too_recent(self):
        # If the source has onset within `after_years` of today, progression
        # cannot fire yet. Force this with a very-young patient whose onset
        # was just sampled.
        yaml = _BASE_HTN_BLOCK.replace("after_years: 5", "after_years: 100")
        mod = load_module_from_str(yaml)
        rng = random.Random(0)
        diagnoses = run_module(
            mod, age_years=35, sex="female", rng=rng, today=date(2026, 1, 1)
        )
        ids = [dx.condition.id for dx in diagnoses]
        assert "essential_hypertension" in ids
        assert "hypertensive_ckd" not in ids

    def test_progressed_condition_carries_progressed_onset(self):
        mod = load_module_from_str(_BASE_HTN_BLOCK)
        rng = random.Random(42)
        diagnoses = run_module(
            mod, age_years=70, sex="male", rng=rng, today=date(2026, 1, 1)
        )
        by_id = {dx.condition.id: dx for dx in diagnoses}
        assert "essential_hypertension" in by_id
        assert "hypertensive_ckd" in by_id
        src = by_id["essential_hypertension"]
        prog = by_id["hypertensive_ckd"]
        # Progressed onset is 5 years after the source onset (after_years=5).
        days_diff = (prog.onset_date - src.onset_date).days
        assert days_diff == 5 * 365

    def test_progression_probability_zero_never_fires(self):
        yaml = _BASE_HTN_BLOCK.replace(
            "        probability: 1.0\n  - id: hypertensive_ckd",
            "        probability: 0.0\n  - id: hypertensive_ckd",
        )
        mod = load_module_from_str(yaml)
        for seed in range(50):
            rng = random.Random(seed)
            diagnoses = run_module(
                mod, age_years=70, sex="male", rng=rng, today=date(2026, 1, 1)
            )
            ids = {dx.condition.id for dx in diagnoses}
            assert "hypertensive_ckd" not in ids

    def test_no_progression_when_source_doesnt_fire(self):
        # Source prevalence 0 → source never fires → progression cannot fire.
        yaml = _BASE_HTN_BLOCK.replace('"0-99": 1.0', '"0-99": 0.0', 1)
        mod = load_module_from_str(yaml)
        for seed in range(50):
            rng = random.Random(seed)
            diagnoses = run_module(
                mod, age_years=70, sex="male", rng=rng, today=date(2026, 1, 1)
            )
            ids = {dx.condition.id for dx in diagnoses}
            assert ids == set()

    def test_progressed_condition_gets_emits_too(self):
        # Target condition has emits — progressions should sample them.
        yaml = """
module: t
version: 0.1.0
conditions:
  - id: htn
    code: {system: s, code: "1", display: htn}
    prevalence: {"0-99": 1.0}
    onset_age: {min: 30, max: 50}
    progressions:
      - to: ckd
        after_years: 5
        probability: 1.0
  - id: ckd
    code: {system: s, code: "2", display: ckd}
    prevalence: {"0-99": 0.0}
    emits:
      - resource_type: Encounter
        spec_id: ckd_visit
        encounter_class: AMB
        type: {system: s, code: "v", display: visit}
"""
        mod = load_module_from_str(yaml)
        rng = random.Random(0)
        diagnoses = run_module(
            mod, age_years=70, sex="male", rng=rng, today=date(2026, 1, 1)
        )
        by_id = {dx.condition.id: dx for dx in diagnoses}
        ckd_dx = by_id["ckd"]
        assert len(ckd_dx.sampled_resources) == 1
        assert ckd_dx.sampled_resources[0].spec_id == "ckd_visit"

    def test_double_fire_dedup_no_double_count(self):
        # If target's prevalence ALSO fires, progression should not overwrite it.
        yaml = """
module: t
version: 0.1.0
conditions:
  - id: htn
    code: {system: s, code: "1", display: htn}
    prevalence: {"0-99": 1.0}
    onset_age: {min: 30, max: 50}
    progressions:
      - to: ckd
        after_years: 5
        probability: 1.0
  - id: ckd
    code: {system: s, code: "2", display: ckd}
    prevalence: {"0-99": 1.0}
"""
        mod = load_module_from_str(yaml)
        rng = random.Random(0)
        diagnoses = run_module(
            mod, age_years=70, sex="male", rng=rng, today=date(2026, 1, 1)
        )
        ids = [dx.condition.id for dx in diagnoses]
        # Each id appears at most once — no double diagnosis.
        assert ids.count("ckd") == 1

    def test_one_hop_only_no_chain_progressions(self):
        # a → b → c. Progression of progression (b → c) must NOT fire in
        # the same run. c only fires if its own prevalence draws it.
        yaml = """
module: t
version: 0.1.0
conditions:
  - id: a
    code: {system: s, code: "1", display: a}
    prevalence: {"0-99": 1.0}
    onset_age: {min: 30, max: 50}
    progressions:
      - to: b
        after_years: 1
        probability: 1.0
  - id: b
    code: {system: s, code: "2", display: b}
    prevalence: {"0-99": 0.0}
    onset_age: {min: 30, max: 50}
    progressions:
      - to: c
        after_years: 1
        probability: 1.0
  - id: c
    code: {system: s, code: "3", display: c}
    prevalence: {"0-99": 0.0}
"""
        mod = load_module_from_str(yaml)
        for seed in range(20):
            rng = random.Random(seed)
            diagnoses = run_module(
                mod, age_years=70, sex="male", rng=rng, today=date(2026, 1, 1)
            )
            ids = {dx.condition.id for dx in diagnoses}
            assert "a" in ids
            assert "b" in ids  # one-hop progression
            assert "c" not in ids  # NOT a chain — second hop never fires

    def test_forward_reference_target_resolves(self):
        # Target declared after source — should still validate and run.
        mod = load_module_from_str(_BASE_HTN_BLOCK)
        # Just verify it loads cleanly; the actual run is covered above.
        ids = [c.id for c in mod.conditions]
        assert ids == ["essential_hypertension", "hypertensive_ckd"]

"""Tests for the progressions-overlay loader.

Overlays are sidecar YAMLs that override matching `(from, to)` progression
rates declared inline in a module YAML. They are the artifact emitted by
`atlas ingest progression`.
"""

from __future__ import annotations

import pytest

from parker_atlas.modules.runtime import (
    ModuleError,
    ProgressionSpec,
    apply_progressions_overlay,
    load_module_from_str,
)


_BASE_MODULE = """
module: htn_overlay_test
version: 0.1.0
conditions:
  - id: essential_hypertension
    code: {system: http://snomed.info/sct, code: "59621000", display: HTN}
    prevalence: {"0-99": 1.0}
    onset_age: {min: 30, max: 50}
    progressions:
      - to: hypertensive_ckd
        after_years: 10
        probability: 0.10
  - id: hypertensive_ckd
    code: {system: http://snomed.info/sct, code: "709044004", display: CKD}
    prevalence: {"0-99": 0.0}
"""


_VALID_OVERLAY = """
module: htn_overlay_test
version: 1.0.0
source:
  name: KDIGO 2024 + USRDS 2023 ADR
  provenance: sourced
  citations:
    - source: KDIGO 2024 CKD Guideline
      url: https://kdigo.org/guidelines/ckd-evaluation-and-management/
progressions:
  - from: essential_hypertension
    to: hypertensive_ckd
    after_years: 12
    probability: 0.105
"""


class TestProgressionsOverlayHappyPath:
    def test_overlay_overrides_inline_rate(self):
        module = load_module_from_str(_BASE_MODULE)
        overlaid = apply_progressions_overlay(module, _VALID_OVERLAY)
        htn = next(c for c in overlaid.conditions if c.id == "essential_hypertension")
        assert htn.progressions == (
            ProgressionSpec(to="hypertensive_ckd", after_years=12, probability=0.105),
        )

    def test_module_unchanged_outside_overlay(self):
        # Non-progression fields on the source condition stay put.
        module = load_module_from_str(_BASE_MODULE)
        overlaid = apply_progressions_overlay(module, _VALID_OVERLAY)
        htn_before = next(c for c in module.conditions if c.id == "essential_hypertension")
        htn_after = next(c for c in overlaid.conditions if c.id == "essential_hypertension")
        assert htn_before.code == htn_after.code
        assert htn_before.prevalence_by_bracket == htn_after.prevalence_by_bracket
        assert htn_before.onset_age == htn_after.onset_age

    def test_target_condition_untouched(self):
        # Only the source's `progressions:` field changes.
        module = load_module_from_str(_BASE_MODULE)
        overlaid = apply_progressions_overlay(module, _VALID_OVERLAY)
        ckd_before = next(c for c in module.conditions if c.id == "hypertensive_ckd")
        ckd_after = next(c for c in overlaid.conditions if c.id == "hypertensive_ckd")
        assert ckd_before == ckd_after

    def test_partial_override_leaves_others_untouched(self):
        # Module declares two progressions; overlay only overrides one.
        base = """
module: t
version: 0.1.0
conditions:
  - id: a
    code: {system: s, code: "1", display: a}
    prevalence: {"0-99": 1.0}
    onset_age: {min: 30, max: 50}
    progressions:
      - to: b
        after_years: 10
        probability: 0.10
      - to: c
        after_years: 5
        probability: 0.05
  - id: b
    code: {system: s, code: "2", display: b}
    prevalence: {"0-99": 0.0}
  - id: c
    code: {system: s, code: "3", display: c}
    prevalence: {"0-99": 0.0}
"""
        overlay = """
module: t
version: 1.0.0
source:
  name: x
  provenance: sourced
progressions:
  - from: a
    to: b
    after_years: 12
    probability: 0.20
"""
        module = load_module_from_str(base)
        overlaid = apply_progressions_overlay(module, overlay)
        a_progs = next(c for c in overlaid.conditions if c.id == "a").progressions
        # Order preserved; only the (a, b) entry is overridden.
        assert a_progs[0] == ProgressionSpec(to="b", after_years=12, probability=0.20)
        assert a_progs[1] == ProgressionSpec(to="c", after_years=5, probability=0.05)


class TestProgressionsOverlayValidation:
    def test_module_name_mismatch_rejected(self):
        bad_overlay = _VALID_OVERLAY.replace("htn_overlay_test", "wrong_module")
        module = load_module_from_str(_BASE_MODULE)
        with pytest.raises(ModuleError, match="declares module='wrong_module'"):
            apply_progressions_overlay(module, bad_overlay)

    def test_placeholder_provenance_rejected(self):
        bad = _VALID_OVERLAY.replace("provenance: sourced", "provenance: placeholder")
        module = load_module_from_str(_BASE_MODULE)
        with pytest.raises(ModuleError, match="must declare source.provenance"):
            apply_progressions_overlay(module, bad)

    def test_missing_provenance_rejected(self):
        bad = """
module: htn_overlay_test
version: 1.0.0
source:
  name: x
progressions:
  - from: essential_hypertension
    to: hypertensive_ckd
    after_years: 10
    probability: 0.10
"""
        module = load_module_from_str(_BASE_MODULE)
        with pytest.raises(ModuleError, match="must declare source.provenance"):
            apply_progressions_overlay(module, bad)

    def test_unknown_progression_pair_rejected(self):
        # Overlay declares a (from, to) pair that doesn't exist in module.
        bad = _VALID_OVERLAY.replace("essential_hypertension", "ghost_condition")
        module = load_module_from_str(_BASE_MODULE)
        with pytest.raises(ModuleError, match="not present in module"):
            apply_progressions_overlay(module, bad)

    def test_missing_required_field_rejected(self):
        bad = """
module: htn_overlay_test
version: 1.0.0
source: {provenance: sourced}
progressions:
  - from: essential_hypertension
    to: hypertensive_ckd
    after_years: 10
    # probability missing
"""
        module = load_module_from_str(_BASE_MODULE)
        with pytest.raises(ModuleError, match="missing 'probability'"):
            apply_progressions_overlay(module, bad)

    def test_probability_out_of_range_rejected(self):
        bad = _VALID_OVERLAY.replace("probability: 0.105", "probability: 1.5")
        module = load_module_from_str(_BASE_MODULE)
        with pytest.raises(ModuleError, match="probability"):
            apply_progressions_overlay(module, bad)

    def test_negative_after_years_rejected(self):
        bad = _VALID_OVERLAY.replace("after_years: 12", "after_years: -1")
        module = load_module_from_str(_BASE_MODULE)
        with pytest.raises(ModuleError, match="after_years"):
            apply_progressions_overlay(module, bad)

    def test_invalid_yaml_rejected(self):
        module = load_module_from_str(_BASE_MODULE)
        with pytest.raises(ModuleError, match="invalid progressions overlay YAML"):
            apply_progressions_overlay(module, "not: valid: yaml: : :")

    def test_top_level_must_be_mapping(self):
        module = load_module_from_str(_BASE_MODULE)
        with pytest.raises(ModuleError, match="must be a YAML mapping"):
            apply_progressions_overlay(module, "- 1\n- 2\n")

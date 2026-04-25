"""Tests for cross-condition `requires` (comorbidity gating within a module)."""

from __future__ import annotations

import random
import textwrap
from datetime import date

import pytest

from parker_atlas.modules import (
    ModuleError,
    load_module_from_str,
    run_module,
)


def _two_condition_module(p_primary: float, p_secondary: float) -> str:
    """Module with primary + secondary that requires it."""
    return textwrap.dedent(
        f"""
        module: t
        version: 0.0.1
        conditions:
          - id: primary
            code:
              system: http://snomed.info/sct
              code: "1"
              display: Primary
            prevalence:
              "0-99": {p_primary}
          - id: secondary
            code:
              system: http://snomed.info/sct
              code: "2"
              display: Secondary
            requires: primary
            prevalence:
              "0-99": {p_secondary}
        """
    )


class TestRequiresParsing:
    def test_parses_string_form(self):
        mod = load_module_from_str(_two_condition_module(0.5, 0.5))
        secondary = mod.conditions[1]
        assert secondary.requires == ("primary",)

    def test_parses_list_form(self):
        mod = load_module_from_str(
            textwrap.dedent(
                """
                module: t
                version: 0.0.1
                conditions:
                  - id: a
                    code: {system: s, code: "1", display: a}
                    prevalence: {"0-99": 1.0}
                  - id: b
                    code: {system: s, code: "2", display: b}
                    prevalence: {"0-99": 1.0}
                  - id: c
                    code: {system: s, code: "3", display: c}
                    requires: [a, b]
                    prevalence: {"0-99": 1.0}
                """
            )
        )
        assert mod.conditions[2].requires == ("a", "b")

    def test_default_requires_is_empty(self):
        mod = load_module_from_str(
            textwrap.dedent(
                """
                module: t
                version: 0.0.1
                conditions:
                  - id: only
                    code: {system: s, code: "1", display: o}
                    prevalence: {"0-99": 1.0}
                """
            )
        )
        assert mod.conditions[0].requires == ()


class TestRequiresValidation:
    def test_rejects_self_reference(self):
        with pytest.raises(ModuleError, match="cannot reference itself"):
            load_module_from_str(
                textwrap.dedent(
                    """
                    module: t
                    version: 0.0.1
                    conditions:
                      - id: x
                        code: {system: s, code: "1", display: x}
                        requires: x
                        prevalence: {"0-99": 1.0}
                    """
                )
            )

    def test_rejects_forward_reference(self):
        # "secondary" lists "primary" in requires, but primary is declared
        # AFTER secondary. Order matters.
        with pytest.raises(ModuleError, match="must reference an earlier-declared"):
            load_module_from_str(
                textwrap.dedent(
                    """
                    module: t
                    version: 0.0.1
                    conditions:
                      - id: secondary
                        code: {system: s, code: "1", display: s}
                        requires: primary
                        prevalence: {"0-99": 1.0}
                      - id: primary
                        code: {system: s, code: "2", display: p}
                        prevalence: {"0-99": 1.0}
                    """
                )
            )

    def test_rejects_unknown_reference(self):
        with pytest.raises(ModuleError, match="must reference an earlier-declared"):
            load_module_from_str(
                textwrap.dedent(
                    """
                    module: t
                    version: 0.0.1
                    conditions:
                      - id: a
                        code: {system: s, code: "1", display: a}
                        requires: nonexistent
                        prevalence: {"0-99": 1.0}
                    """
                )
            )

    def test_rejects_duplicate_condition_id(self):
        with pytest.raises(ModuleError, match="duplicate condition id"):
            load_module_from_str(
                textwrap.dedent(
                    """
                    module: t
                    version: 0.0.1
                    conditions:
                      - id: dup
                        code: {system: s, code: "1", display: a}
                        prevalence: {"0-99": 1.0}
                      - id: dup
                        code: {system: s, code: "2", display: b}
                        prevalence: {"0-99": 1.0}
                    """
                )
            )


class TestRequiresRuntime:
    def test_secondary_fires_only_when_primary_fires(self):
        # Primary p=1, secondary p=1: secondary always fires.
        mod = load_module_from_str(_two_condition_module(1.0, 1.0))
        rng = random.Random(0)
        diagnoses = run_module(
            mod, age_years=50, sex="female", rng=rng, today=date(2026, 4, 25)
        )
        ids = {d.condition.id for d in diagnoses}
        assert ids == {"primary", "secondary"}

    def test_secondary_skipped_when_primary_does_not_fire(self):
        # Primary p=0, secondary p=1: secondary never fires.
        mod = load_module_from_str(_two_condition_module(0.0, 1.0))
        rng = random.Random(0)
        out = run_module(
            mod, age_years=50, sex="female", rng=rng, today=date(2026, 4, 25)
        )
        assert out == []

    def test_secondary_probability_applies_only_to_eligible(self):
        # Primary p=1, secondary p=0.3 → secondary should fire ~30% of runs.
        mod = load_module_from_str(_two_condition_module(1.0, 0.3))
        rng = random.Random(0)
        secondary_hits = 0
        n = 1000
        for _ in range(n):
            diagnoses = run_module(
                mod, age_years=50, sex="female", rng=rng, today=date(2026, 4, 25)
            )
            ids = {d.condition.id for d in diagnoses}
            assert "primary" in ids  # primary always fires at p=1
            if "secondary" in ids:
                secondary_hits += 1
        # Expect within ~3pp of 0.30 at N=1000.
        assert abs(secondary_hits / n - 0.30) < 0.05

    def test_multi_dependency_requires_all_to_fire(self):
        mod = load_module_from_str(
            textwrap.dedent(
                """
                module: t
                version: 0.0.1
                conditions:
                  - id: a
                    code: {system: s, code: "1", display: a}
                    prevalence: {"0-99": 0.5}
                  - id: b
                    code: {system: s, code: "2", display: b}
                    prevalence: {"0-99": 0.5}
                  - id: c
                    code: {system: s, code: "3", display: c}
                    requires: [a, b]
                    prevalence: {"0-99": 1.0}
                """
            )
        )
        rng = random.Random(7)
        n = 1000
        only_when_both = 0
        c_with_one_missing = 0
        for _ in range(n):
            diagnoses = run_module(
                mod, age_years=50, sex="female", rng=rng, today=date(2026, 4, 25)
            )
            ids = {d.condition.id for d in diagnoses}
            if "c" in ids:
                if {"a", "b"}.issubset(ids):
                    only_when_both += 1
                else:
                    c_with_one_missing += 1
        # c only fires when both a and b are present.
        assert c_with_one_missing == 0
        # And it fires roughly p(a) * p(b) * p(c) = 0.25 of the time.
        assert 0.18 <= only_when_both / n <= 0.32


class TestRequiresIntegration:
    def test_chains_three_levels(self):
        # primary → secondary → tertiary; all must chain to reach tertiary.
        mod = load_module_from_str(
            textwrap.dedent(
                """
                module: t
                version: 0.0.1
                conditions:
                  - id: primary
                    code: {system: s, code: "1", display: p}
                    prevalence: {"0-99": 1.0}
                  - id: secondary
                    code: {system: s, code: "2", display: s}
                    requires: primary
                    prevalence: {"0-99": 0.0}
                  - id: tertiary
                    code: {system: s, code: "3", display: t}
                    requires: secondary
                    prevalence: {"0-99": 1.0}
                """
            )
        )
        rng = random.Random(0)
        diagnoses = run_module(
            mod, age_years=50, sex="female", rng=rng, today=date(2026, 4, 25)
        )
        ids = {d.condition.id for d in diagnoses}
        # primary fires (p=1), secondary doesn't (p=0), so tertiary must
        # not fire even though tertiary's own prevalence is 1.0.
        assert ids == {"primary"}

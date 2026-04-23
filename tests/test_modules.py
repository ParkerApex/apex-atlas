"""Tests for the clinical module runtime and bundled modules."""

from __future__ import annotations

import random
import textwrap

import pytest

from parker_atlas.modules import (
    ModuleError,
    list_bundled_modules,
    load_module,
    load_module_from_str,
    run_module,
)


class TestLoader:
    def test_parses_minimal_module(self):
        yaml_text = textwrap.dedent(
            """
            module: t1
            version: 0.0.1
            description: test
            conditions:
              - id: foo
                code: {system: http://snomed.info/sct, code: "1", display: Foo}
                prevalence:
                  "0-99": 0.5
            """
        )
        mod = load_module_from_str(yaml_text)
        assert mod.name == "t1"
        assert mod.version == "0.0.1"
        assert len(mod.conditions) == 1
        assert mod.conditions[0].id == "foo"

    def test_rejects_missing_required_fields(self):
        with pytest.raises(ModuleError, match="required"):
            load_module_from_str("version: 0.0.1\nconditions: []")

    def test_rejects_non_mapping_top_level(self):
        with pytest.raises(ModuleError, match="mapping"):
            load_module_from_str("- just\n- a\n- list")

    def test_rejects_malformed_bracket(self):
        yaml_text = textwrap.dedent(
            """
            module: t2
            version: 0.0.1
            conditions:
              - id: c
                code: {system: s, code: c, display: d}
                prevalence:
                  "bogus": 0.1
            """
        )
        with pytest.raises(ModuleError, match="bracket"):
            load_module_from_str(yaml_text)

    def test_parses_sex_stratified_prevalence(self):
        yaml_text = textwrap.dedent(
            """
            module: t3
            version: 0.0.1
            conditions:
              - id: c
                code: {system: s, code: c, display: d}
                prevalence:
                  female:
                    "0-99": 0.3
                  male:
                    "0-99": 0.7
            """
        )
        mod = load_module_from_str(yaml_text)
        stratified = mod.conditions[0].prevalence_by_sex
        assert stratified is not None
        assert stratified["female"][(0, 99)] == 0.3
        assert stratified["male"][(0, 99)] == 0.7

    def test_bundled_hypertension_loads(self):
        mod = load_module("hypertension")
        assert mod.name == "hypertension"
        assert any(c.id == "essential_hypertension" for c in mod.conditions)
        assert mod.cites, "hypertension should carry at least one citation"

    def test_list_bundled_modules_includes_hypertension(self):
        assert "hypertension" in list_bundled_modules()

    def test_load_missing_module_raises(self):
        with pytest.raises(ModuleError, match="no bundled module"):
            load_module("not-a-real-module")


class TestRuntime:
    def _mod(self, yaml_text: str):
        return load_module_from_str(textwrap.dedent(yaml_text))

    def test_always_fires_when_probability_is_one(self):
        mod = self._mod(
            """
            module: always
            version: 0.0.1
            conditions:
              - id: c
                code: {system: s, code: c, display: d}
                prevalence:
                  "0-99": 1.0
            """
        )
        rng = random.Random(0)
        diagnoses = run_module(mod, age_years=30, sex="female", rng=rng)
        assert len(diagnoses) == 1
        assert diagnoses[0].condition.id == "c"

    def test_never_fires_when_probability_is_zero(self):
        mod = self._mod(
            """
            module: never
            version: 0.0.1
            conditions:
              - id: c
                code: {system: s, code: c, display: d}
                prevalence:
                  "0-99": 0.0
            """
        )
        rng = random.Random(0)
        assert run_module(mod, age_years=30, sex="female", rng=rng) == []

    def test_respects_age_bracket(self):
        mod = self._mod(
            """
            module: bracketed
            version: 0.0.1
            conditions:
              - id: c
                code: {system: s, code: c, display: d}
                prevalence:
                  "0-17": 0.0
                  "18-99": 1.0
            """
        )
        rng = random.Random(0)
        assert run_module(mod, age_years=10, sex="female", rng=rng) == []
        adult = run_module(mod, age_years=50, sex="female", rng=rng)
        assert len(adult) == 1

    def test_respects_sex_stratification(self):
        mod = self._mod(
            """
            module: stratified
            version: 0.0.1
            conditions:
              - id: c
                code: {system: s, code: c, display: d}
                prevalence:
                  female:
                    "0-99": 1.0
                  male:
                    "0-99": 0.0
            """
        )
        rng = random.Random(0)
        assert len(run_module(mod, age_years=30, sex="female", rng=rng)) == 1
        assert run_module(mod, age_years=30, sex="male", rng=rng) == []

    def test_reproducible_with_seed(self):
        mod = load_module("hypertension")
        r1 = random.Random(42)
        r2 = random.Random(42)
        a = [run_module(mod, age_years=50, sex="female", rng=r1) for _ in range(20)]
        b = [run_module(mod, age_years=50, sex="female", rng=r2) for _ in range(20)]
        assert a == b

    def test_hypertension_prevalence_is_roughly_in_range(self):
        """Rough sanity check: ~50% of middle-aged patients should hit over 1000 trials."""
        mod = load_module("hypertension")
        rng = random.Random(1)
        hits = sum(
            1 for _ in range(2000) if run_module(mod, age_years=45, sex="female", rng=rng)
        )
        # The module specifies 0.47 for 35-54. Be loose to avoid flakiness.
        assert 800 < hits < 1200

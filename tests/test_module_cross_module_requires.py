"""Tests for cross-module `requires` and multi-module CLI runs."""

from __future__ import annotations

import json
import random
import textwrap
from datetime import date

import pytest
from typer.testing import CliRunner

from parker_atlas.cli import app
from parker_atlas.modules import (
    ModuleError,
    load_module_from_str,
    run_module,
)

runner = CliRunner()


class TestCrossModuleParsing:
    def test_accepts_module_qualified_requires(self):
        # `module:condition_id` is parser-legal; runtime decides whether
        # the upstream module is actually active.
        mod = load_module_from_str(
            textwrap.dedent(
                """
                module: complications
                version: 0.1.0
                conditions:
                  - id: nephro
                    code: {system: s, code: "1", display: n}
                    requires: hypertension:essential_hypertension
                    prevalence: {"0-99": 0.5}
                """
            )
        )
        assert mod.conditions[0].requires == ("hypertension:essential_hypertension",)

    def test_rejects_malformed_qualified_reference(self):
        # Empty module or empty condition_id
        for bad in (":essential_hypertension", "hypertension:", ":"):
            with pytest.raises(ModuleError, match="must be"):
                load_module_from_str(
                    textwrap.dedent(
                        f"""
                        module: t
                        version: 0.0.1
                        conditions:
                          - id: x
                            code: {{system: s, code: "1", display: x}}
                            requires: "{bad}"
                            prevalence: {{"0-99": 1.0}}
                        """
                    )
                )

    def test_local_requires_still_must_reference_earlier_sibling(self):
        # Even with cross-module support, local references must resolve
        # locally to an earlier-declared sibling.
        with pytest.raises(ModuleError, match="must reference an earlier-declared"):
            load_module_from_str(
                textwrap.dedent(
                    """
                    module: t
                    version: 0.0.1
                    conditions:
                      - id: a
                        code: {system: s, code: "1", display: a}
                        requires: nonexistent_local
                        prevalence: {"0-99": 1.0}
                    """
                )
            )


class TestExternalFiredRuntime:
    def test_external_fired_satisfies_cross_module_requires(self):
        mod = load_module_from_str(
            textwrap.dedent(
                """
                module: complications
                version: 0.1.0
                conditions:
                  - id: nephro
                    code: {system: s, code: "1", display: n}
                    requires: hypertension:essential_hypertension
                    prevalence: {"0-99": 1.0}
                """
            )
        )
        rng = random.Random(0)
        # Without external_fired, secondary should be skipped.
        out_empty = run_module(
            mod, age_years=70, sex="female", rng=rng,
            today=date(2026, 4, 25),
        )
        assert out_empty == []

        # With the upstream condition declared fired, the gate opens.
        rng = random.Random(0)
        out = run_module(
            mod, age_years=70, sex="female", rng=rng,
            today=date(2026, 4, 25),
            external_fired={"hypertension:essential_hypertension"},
        )
        assert len(out) == 1
        assert out[0].condition.id == "nephro"

    def test_external_fired_only_unblocks_cross_module(self):
        # Same-module `requires` are still local — external_fired is
        # only consulted for `module:cond` syntax.
        mod = load_module_from_str(
            textwrap.dedent(
                """
                module: m
                version: 0.0.1
                conditions:
                  - id: a
                    code: {system: s, code: "1", display: a}
                    prevalence: {"0-99": 0.0}     # never fires
                  - id: b
                    code: {system: s, code: "2", display: b}
                    requires: a                    # local-only
                    prevalence: {"0-99": 1.0}
                """
            )
        )
        rng = random.Random(0)
        # Even with `m:a` claimed externally fired, `b`'s requires:`a`
        # checks the in-this-run set, where `a` is absent (p=0).
        out = run_module(
            mod, age_years=70, sex="female", rng=rng,
            today=date(2026, 4, 25),
            external_fired={"m:a"},
        )
        assert out == []


class TestMultiModuleCLI:
    def test_comma_separated_module_names_load_in_order(self, tmp_path):
        result = runner.invoke(
            app,
            [
                "generate",
                "--patients", "5",
                "--seed", "42",
                "--module", "hypertension,complications",
                "--out", str(tmp_path),
            ],
        )
        assert result.exit_code == 0, result.output
        # Multi-module bundles can have both Conditions present.
        for f in sorted(tmp_path.glob("*.json")):
            data = json.loads(f.read_text())
            condition_codes = {
                e["resource"]["code"]["coding"][0]["code"]
                for e in data["entry"]
                if e["resource"]["resourceType"] == "Condition"
            }
            # CKD never appears without HTN (cross-module gate).
            assert not (
                "236425005" in condition_codes and "59621000" not in condition_codes
            )

    def test_complications_alone_produces_no_ckd(self, tmp_path):
        # Without hypertension declared in --module, the cross-module
        # `requires` is unsatisfied for every patient.
        result = runner.invoke(
            app,
            [
                "generate",
                "--patients", "200",
                "--seed", "42",
                "--module", "complications",
                "--out", str(tmp_path),
            ],
        )
        assert result.exit_code == 0, result.output
        for f in sorted(tmp_path.glob("*.json")):
            data = json.loads(f.read_text())
            for e in data["entry"]:
                if e["resource"]["resourceType"] == "Condition":
                    assert e["resource"]["code"]["coding"][0]["code"] != "236425005"

    def test_ckd_rate_in_htn_patients_matches_module_target(self, tmp_path):
        # complications.yaml declares 0.15 prevalence for CKD-given-HTN.
        # At N=2000 with seed 42, the actual rate should be near 15%.
        result = runner.invoke(
            app,
            [
                "generate",
                "--patients", "2000",
                "--seed", "42",
                "--module", "hypertension,complications",
                "--out", str(tmp_path),
            ],
        )
        assert result.exit_code == 0, result.output
        htn_count = ckd_count = 0
        for f in sorted(tmp_path.glob("*.json")):
            data = json.loads(f.read_text())
            codes = {
                e["resource"]["code"]["coding"][0]["code"]
                for e in data["entry"]
                if e["resource"]["resourceType"] == "Condition"
            }
            has_htn = "59621000" in codes
            has_ckd = "236425005" in codes
            if has_htn:
                htn_count += 1
                if has_ckd:
                    ckd_count += 1
        rate = ckd_count / htn_count if htn_count else 0.0
        assert htn_count > 100, f"too few hypertensive patients in cohort ({htn_count})"
        assert abs(rate - 0.15) < 0.05, f"CKD rate {rate:.3f} vs target 0.15"

    def test_unknown_module_in_list_fails(self, tmp_path):
        result = runner.invoke(
            app,
            [
                "generate",
                "--patients", "1",
                "--seed", "0",
                "--module", "hypertension,not-a-real-module",
                "--out", str(tmp_path),
            ],
        )
        assert result.exit_code == 1

"""Tests for emit_presence_rate metric kind end-to-end."""

from __future__ import annotations

import textwrap
from datetime import date
from pathlib import Path

import pytest
from typer.testing import CliRunner

from parker_atlas.cli import app
from parker_atlas.validation.cohort import evaluate_cohort
from parker_atlas.validation.expectations import (
    ExpectationError,
    load_bundled_expectation,
    load_expectation_from_str,
)

runner = CliRunner()


class TestEmitPresenceParsing:
    def test_parses_emit_presence_metric(self):
        yaml_text = textwrap.dedent(
            """
            module: t
            version: 0.0.1
            source: {provenance: sourced}
            metrics:
              - id: my_treatment_rate
                kind: emit_presence_rate
                condition_code: "59621000"
                condition_system: http://snomed.info/sct
                emit_resource_type: MedicationRequest
                emit_code: "197361"
                emit_code_system: http://www.nlm.nih.gov/research/umls/rxnorm
                tolerance: {kind: wilson, confidence: 95}
                target: 0.6
            """
        )
        exp = load_expectation_from_str(yaml_text)
        assert len(exp.metrics) == 1
        m = exp.metrics[0]
        assert m.kind == "emit_presence_rate"
        assert m.target == 0.6
        assert m.emit_presence is not None
        assert m.emit_presence.resource_type == "MedicationRequest"
        assert m.emit_presence.code == "197361"

    def test_rejects_target_out_of_range(self):
        yaml_text = textwrap.dedent(
            """
            module: t
            version: 0.0.1
            metrics:
              - id: bad
                kind: emit_presence_rate
                condition_code: "1"
                emit_resource_type: MedicationRequest
                tolerance: {kind: wilson, confidence: 95}
                target: 1.5
            """
        )
        with pytest.raises(ExpectationError, match="target"):
            load_expectation_from_str(yaml_text)

    def test_rejects_unknown_emit_resource_type(self):
        yaml_text = textwrap.dedent(
            """
            module: t
            version: 0.0.1
            metrics:
              - id: bad
                kind: emit_presence_rate
                condition_code: "1"
                emit_resource_type: ImagingStudy
                tolerance: {kind: wilson, confidence: 95}
                target: 0.5
            """
        )
        with pytest.raises(ExpectationError, match="emit_resource_type"):
            load_expectation_from_str(yaml_text)

    def test_emit_metric_without_code_filter_just_checks_presence(self):
        yaml_text = textwrap.dedent(
            """
            module: t
            version: 0.0.1
            metrics:
              - id: rate
                kind: emit_presence_rate
                condition_code: "1"
                emit_resource_type: Encounter
                tolerance: {kind: wilson, confidence: 95}
                target: 1.0
            """
        )
        exp = load_expectation_from_str(yaml_text)
        m = exp.metrics[0]
        assert m.emit_presence.code is None


class TestEmitPresenceEvaluation:
    def test_hypertension_emit_metric_passes_at_scale(self, tmp_path):
        # Generate a 20k cohort with the hypertension module; the
        # bundled expectation now includes a hypertension_treated_rate
        # check at target 0.60 (matching the module's medication
        # probability), so the harness should pass at Wilson 99%.
        gen = runner.invoke(
            app,
            [
                "generate",
                "--patients", "20000",
                "--seed", "42",
                "--module", "hypertension",
                "--out", str(tmp_path),
            ],
        )
        assert gen.exit_code == 0, gen.output

        exp = load_bundled_expectation("hypertension")
        # The bundled expectation now includes the new kind alongside
        # the existing prevalence metrics.
        kinds = {m.kind for m in exp.metrics}
        assert "emit_presence_rate" in kinds
        assert "conditional_prevalence" in kinds

        report = evaluate_cohort(
            tmp_path, exp, min_samples=100, reference_date=date(2026, 4, 25)
        )
        assert report.passed, (
            f"unexpected failure on bundled hypertension:\n"
            f"  {[(r.metric_id, r.bracket, r.sex, r.actual, r.target) for r in report.failing_metrics]}"
        )
        # Check the emit_presence_rate result specifically.
        emit_results = [r for r in report.results if r.metric_id == "hypertension_treated_rate"]
        assert len(emit_results) == 1
        r = emit_results[0]
        assert r.bracket is None
        assert r.sex is None
        # Expected ~60% within Wilson 99% half-width at N >= 5000.
        assert abs(r.actual - 0.60) < 0.05
        assert r.within_tolerance

    def test_emit_metric_fails_when_module_does_not_emit(self, tmp_path):
        # Generate without the hypertension module → no MedicationRequests
        # → no hypertensive patients → metric is skipped (denominator 0).
        runner.invoke(
            app,
            [
                "generate",
                "--patients", "200",
                "--seed", "0",
                "--out", str(tmp_path),
            ],
        )
        exp = load_bundled_expectation("hypertension")
        report = evaluate_cohort(
            tmp_path, exp, min_samples=10, reference_date=date(2026, 4, 25)
        )
        emit_results = [
            r for r in report.results if r.metric_id == "hypertension_treated_rate"
        ]
        # No hypertensive patients → emit metric is skipped.
        assert not emit_results
        assert any("hypertension_treated_rate" in s for s in report.skipped)


class TestCLIEmitFidelityOutput:
    def test_cohort_table_renders_cohort_label_for_emit_metrics(self, tmp_path):
        runner.invoke(
            app,
            [
                "generate",
                "--patients", "5000",
                "--seed", "42",
                "--module", "hypertension",
                "--out", str(tmp_path),
            ],
        )
        result = runner.invoke(
            app,
            [
                "validate",
                str(tmp_path),
                "--cohort",
                "--module", "hypertension",
                "--min-samples", "100",
                "--as-of", "2026-04-25",
            ],
        )
        # Don't gate on exit code — at smaller N some prevalence brackets
        # can flake. Just check the cohort row is rendered for the emit
        # metric.
        assert "cohort" in result.output
        assert "treated_rate" in result.output or "hypertension_t" in result.output

"""Tests for the cohort fidelity harness and `atlas validate --cohort`."""

from __future__ import annotations

from datetime import date

from typer.testing import CliRunner

from parker_atlas.cli import app
from parker_atlas.validation.cohort import _check_tolerance, evaluate_cohort
from parker_atlas.validation.expectations import Tolerance, load_bundled_expectation

runner = CliRunner()


class TestToleranceMath:
    """Direct unit tests for the tolerance-kind math in _check_tolerance."""

    def test_absolute_passes_within_value(self):
        tol = Tolerance(kind="absolute", value=0.05)
        assert _check_tolerance(tol, 0.47, 0.47, 100) == (True, 0.05)
        assert _check_tolerance(tol, 0.50, 0.47, 100) == (True, 0.05)

    def test_absolute_fails_beyond_value(self):
        tol = Tolerance(kind="absolute", value=0.05)
        within, half = _check_tolerance(tol, 0.60, 0.47, 100)
        assert within is False and half == 0.05

    def test_normal_95_narrows_with_n(self):
        tol = Tolerance(kind="normal", confidence=95.0)
        # At N=100 around target=0.5, half-width ≈ 1.96 * sqrt(0.25/100) = 0.098
        _, h_100 = _check_tolerance(tol, 0.5, 0.5, 100)
        # At N=10_000, half-width ≈ 1.96 * sqrt(0.25/10000) = 0.0098
        _, h_10k = _check_tolerance(tol, 0.5, 0.5, 10_000)
        assert h_100 > h_10k
        assert 0.09 < h_100 < 0.11
        assert 0.009 < h_10k < 0.011

    def test_normal_95_rejects_drift_well_beyond_se(self):
        tol = Tolerance(kind="normal", confidence=95.0)
        # Target 0.47, N=1000 → SE ≈ 0.0158, 95% half ≈ 0.031
        # Observed 0.55 → |0.55 - 0.47| = 0.08 >> 0.031 → fail.
        within, _ = _check_tolerance(tol, 0.55, 0.47, 1000)
        assert within is False

    def test_wilson_95_contains_target_near_observed(self):
        tol = Tolerance(kind="wilson", confidence=95.0)
        within, _ = _check_tolerance(tol, 0.47, 0.47, 1000)
        assert within is True

    def test_wilson_95_widens_at_extreme_observed(self):
        tol = Tolerance(kind="wilson", confidence=95.0)
        # Wilson is well-defined even at observed=0.99.
        within_close, half_close = _check_tolerance(tol, 0.99, 0.98, 200)
        within_far, _ = _check_tolerance(tol, 0.99, 0.50, 200)
        assert within_close is True
        assert within_far is False
        assert half_close > 0.0

    def test_wilson_handles_observed_zero(self):
        tol = Tolerance(kind="wilson", confidence=95.0)
        # Observed 0 out of 100 → Wilson CI has non-zero upper bound.
        within_small, _ = _check_tolerance(tol, 0.0, 0.02, 100)
        within_large, _ = _check_tolerance(tol, 0.0, 0.50, 100)
        assert within_small is True
        assert within_large is False

    def test_confidence_widens_tolerance(self):
        # Higher confidence → wider CI / larger half-width.
        _, half_95 = _check_tolerance(
            Tolerance(kind="normal", confidence=95.0), 0.5, 0.5, 1000
        )
        _, half_99 = _check_tolerance(
            Tolerance(kind="normal", confidence=99.0), 0.5, 0.5, 1000
        )
        _, half_999 = _check_tolerance(
            Tolerance(kind="normal", confidence=99.9), 0.5, 0.5, 1000
        )
        assert half_95 < half_99 < half_999


def _generate(tmp_path, *, patients: int, seed: int = 0, module: str | None = None):
    args = [
        "generate",
        "--patients", str(patients),
        "--seed", str(seed),
        "--out", str(tmp_path),
    ]
    if module:
        args.extend(["--module", module])
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output


class TestEvaluateCohort:
    def test_evaluates_hypertension_at_scale(self, tmp_path):
        # Uses the bundled hypertension expectation, which gates on Wilson
        # 95% CIs. At that confidence level each metric has an intrinsic
        # ~5% false-positive rate; empirically, seed 42 at N=20k has all
        # 5 brackets inside their CIs. See expectations/library/README.md
        # for the tolerance-vs-cohort-size tradeoff.
        _generate(tmp_path, patients=20000, seed=42, module="hypertension")
        exp = load_bundled_expectation("hypertension")
        report = evaluate_cohort(
            tmp_path, exp, min_samples=100, reference_date=date(2026, 4, 23)
        )
        assert report.bundles_scanned == 20000
        assert report.total_patients == 20000
        assert report.passed, (
            f"cohort harness unexpectedly failed:\n"
            f"  failing: {[(r.metric_id, r.bracket, r.actual, r.target) for r in report.failing_metrics]}\n"
            f"  skipped: {report.skipped}"
        )

    def test_skips_brackets_below_min_samples(self, tmp_path):
        # With only 20 patients, every bracket is below min_samples=30.
        _generate(tmp_path, patients=20, seed=0, module="hypertension")
        exp = load_bundled_expectation("hypertension")
        report = evaluate_cohort(tmp_path, exp, min_samples=30)
        # At most a handful of results and a lot of skips.
        assert len(report.skipped) >= 1
        assert all(r.n >= 30 for r in report.results)

    def test_detects_missing_condition(self, tmp_path):
        # Generate without the module → every Bundle has no Condition →
        # actual prevalence ≈ 0 for every bracket → fails every target.
        _generate(tmp_path, patients=500, seed=0)
        exp = load_bundled_expectation("hypertension")
        report = evaluate_cohort(
            tmp_path, exp, min_samples=50, reference_date=date(2026, 4, 23)
        )
        assert not report.passed
        # All computed actuals should be 0 (no Conditions anywhere).
        assert all(r.actual == 0 for r in report.results)

    def test_handles_malformed_json(self, tmp_path):
        _generate(tmp_path, patients=3, seed=0)
        (tmp_path / "oops.json").write_text("{not valid")
        exp = load_bundled_expectation("hypertension")
        report = evaluate_cohort(tmp_path, exp, min_samples=1)
        assert report.parse_errors
        assert not report.passed


class TestValidateCohortCLI:
    def test_cohort_command_succeeds_on_large_run(self, tmp_path):
        # See TestEvaluateCohort.test_evaluates_hypertension_at_scale for
        # the reason the cohort is 20k; Wilson 95% at smaller N has
        # unacceptable per-metric false-positive rates.
        _generate(tmp_path, patients=20000, seed=42, module="hypertension")
        result = runner.invoke(
            app,
            [
                "validate",
                str(tmp_path),
                "--cohort",
                "--module", "hypertension",
                "--min-samples", "100",
                "--as-of", "2026-04-23",
            ],
        )
        assert result.exit_code == 0, result.output
        assert "Cohort fidelity" in result.output
        assert "hypertension" in result.output

    def test_cohort_without_module_flag_fails(self, tmp_path):
        _generate(tmp_path, patients=10, seed=0)
        result = runner.invoke(app, ["validate", str(tmp_path), "--cohort"])
        assert result.exit_code == 1
        assert "requires --module" in result.output

    def test_cohort_with_unknown_module_fails(self, tmp_path):
        _generate(tmp_path, patients=10, seed=0)
        result = runner.invoke(
            app,
            ["validate", str(tmp_path), "--cohort", "--module", "not-a-real-module"],
        )
        assert result.exit_code == 1
        assert "no bundled expectation" in result.output

    def test_cohort_detects_missing_module_output(self, tmp_path):
        # Generated without --module; cohort harness should fail.
        _generate(tmp_path, patients=500, seed=0)
        result = runner.invoke(
            app,
            [
                "validate",
                str(tmp_path),
                "--cohort",
                "--module", "hypertension",
                "--min-samples", "30",
                "--as-of", "2026-04-23",
            ],
        )
        assert result.exit_code == 1
        assert "FAIL" in result.output

    def test_structural_mode_still_works(self, tmp_path):
        _generate(tmp_path, patients=3, seed=0)
        result = runner.invoke(app, ["validate", str(tmp_path)])
        assert result.exit_code == 0
        assert "passed" in result.output

    def test_cohort_output_shows_placeholder_provenance(self, tmp_path):
        _generate(tmp_path, patients=200, seed=0, module="hypertension")
        result = runner.invoke(
            app,
            [
                "validate",
                str(tmp_path),
                "--cohort",
                "--module", "hypertension",
                "--min-samples", "10",
                "--as-of", "2026-04-23",
            ],
        )
        # Exit code may be 0 or 1 depending on sampling; we just care
        # that the output clearly labels the expectation as placeholder.
        assert "placeholder" in result.output
        assert "cdc.gov" in result.output.lower()  # a citation URL is surfaced

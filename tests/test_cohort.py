"""Tests for the cohort fidelity harness and `atlas validate --cohort`."""

from __future__ import annotations

from datetime import date

from typer.testing import CliRunner

from parker_atlas.cli import app
from parker_atlas.validation.cohort import evaluate_cohort
from parker_atlas.validation.expectations import load_bundled_expectation

runner = CliRunner()


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
        # A 5,000-patient cohort with the hypertension module should satisfy
        # the declared ±0.05 tolerance on every bracket with N >= min_samples.
        _generate(tmp_path, patients=5000, seed=42, module="hypertension")
        exp = load_bundled_expectation("hypertension")
        report = evaluate_cohort(
            tmp_path, exp, min_samples=100, reference_date=date(2026, 4, 23)
        )
        assert report.bundles_scanned == 5000
        assert report.total_patients == 5000
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
        # Use 5k patients so the 75-95 bracket (~7% of the pyramid) has
        # enough N that sampling variance fits under the ±0.05 tolerance.
        _generate(tmp_path, patients=5000, seed=42, module="hypertension")
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

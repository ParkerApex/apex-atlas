"""Tests for the NDJSON path of the cohort fidelity harness."""

from __future__ import annotations

from datetime import date

from typer.testing import CliRunner

from parker_atlas.cli import app
from parker_atlas.validation.cohort import evaluate_cohort
from parker_atlas.validation.expectations import load_bundled_expectation

runner = CliRunner()


def _generate_ndjson(tmp_path, *, patients: int, seed: int = 42, module: str = "hypertension"):
    r = runner.invoke(
        app,
        [
            "generate",
            "--patients", str(patients),
            "--seed", str(seed),
            "--module", module,
            "--format", "ndjson",
            "--out", str(tmp_path),
        ],
    )
    assert r.exit_code == 0, r.output


class TestNDJSONLoader:
    def test_evaluate_cohort_works_on_ndjson_directory(self, tmp_path):
        _generate_ndjson(tmp_path, patients=20000)
        exp = load_bundled_expectation("hypertension")
        report = evaluate_cohort(
            tmp_path, exp, min_samples=100, reference_date=date(2026, 4, 25)
        )
        assert report.bundles_scanned == 20000
        assert report.total_patients == 20000
        assert report.passed, (
            f"NDJSON cohort harness failed:\n"
            f"  failing: {[(r.metric_id, r.bracket, r.sex, r.actual, r.target) for r in report.failing_metrics]}"
        )

    def test_ndjson_path_yields_same_results_as_bundle_path(self, tmp_path):
        bundle_dir = tmp_path / "bundles"
        ndjson_dir = tmp_path / "ndjson"
        for fmt, out in (("fhir-r4", bundle_dir), ("ndjson", ndjson_dir)):
            r = runner.invoke(
                app,
                [
                    "generate", "--patients", "5000",
                    "--seed", "42", "--module", "hypertension",
                    "--format", fmt, "--out", str(out),
                ],
            )
            assert r.exit_code == 0, r.output

        exp = load_bundled_expectation("hypertension")
        bundle_report = evaluate_cohort(
            bundle_dir, exp, min_samples=100, reference_date=date(2026, 4, 25)
        )
        ndjson_report = evaluate_cohort(
            ndjson_dir, exp, min_samples=100, reference_date=date(2026, 4, 25)
        )
        # Same cohort, same metrics → same actuals down to the float.
        assert bundle_report.total_patients == ndjson_report.total_patients
        bundle_actuals = {
            (r.metric_id, r.bracket, r.sex): r.actual
            for r in bundle_report.results
        }
        ndjson_actuals = {
            (r.metric_id, r.bracket, r.sex): r.actual
            for r in ndjson_report.results
        }
        assert bundle_actuals == ndjson_actuals

    def test_cross_module_metric_works_on_ndjson(self, tmp_path):
        # Multi-module + cross-module fidelity on NDJSON output.
        r = runner.invoke(
            app,
            [
                "generate",
                "--patients", "5000",
                "--seed", "42",
                "--module", "hypertension,complications",
                "--format", "ndjson",
                "--out", str(tmp_path),
            ],
        )
        assert r.exit_code == 0, r.output

        exp = load_bundled_expectation("complications")
        report = evaluate_cohort(
            tmp_path, exp, min_samples=100, reference_date=date(2026, 4, 25)
        )
        assert report.passed
        # Single metric: htn_to_ckd_progression_rate at target 0.15.
        assert len(report.results) == 1
        result = report.results[0]
        assert abs(result.actual - 0.15) < 0.05

    def test_orphan_resources_skipped_safely(self, tmp_path):
        _generate_ndjson(tmp_path, patients=5)
        # Append an orphan Condition referencing an unknown patient.
        cond_file = tmp_path / "Condition.ndjson"
        if not cond_file.exists():
            cond_file.write_text("")
        cond_file.write_text(
            cond_file.read_text()
            + '{"resourceType":"Condition","subject":{"reference":"urn:uuid:does-not-exist"},'
              '"code":{"coding":[{"system":"http://snomed.info/sct","code":"foo"}]}}\n'
        )
        # Harness should not error — it just skips the orphan.
        exp = load_bundled_expectation("hypertension")
        report = evaluate_cohort(
            tmp_path, exp, min_samples=1, reference_date=date(2026, 4, 25)
        )
        assert not report.parse_errors
        assert report.total_patients == 5

    def test_empty_directory_produces_no_patients(self, tmp_path):
        # No Patient.ndjson, no Bundle JSON → harness reports zero
        # patients. Existing CLI behavior surfaces "no Bundles found".
        exp = load_bundled_expectation("hypertension")
        report = evaluate_cohort(
            tmp_path, exp, min_samples=1, reference_date=date(2026, 4, 25)
        )
        assert report.bundles_scanned == 0
        assert report.total_patients == 0


class TestNDJSONCohortCLI:
    def test_cli_passes_on_ndjson_cohort(self, tmp_path):
        _generate_ndjson(tmp_path, patients=20000)
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
        assert result.exit_code == 0, result.output
        assert "Cohort fidelity" in result.output

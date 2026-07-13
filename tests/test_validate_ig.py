"""Tests for the `atlas validate --ig` conformance harness (native path)."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from parker_atlas.cli import app
from parker_atlas.validation.ig import render_report, run_ig_validation

runner = CliRunner()


def _write_ndjson(path, rows):
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def _valid_dataset(tmp_path):
    _write_ndjson(tmp_path / "Patient.ndjson", [
        {"resourceType": "Patient", "id": "P1",
         "meta": {"profile": ["http://hl7.org/fhir/us/core/StructureDefinition/us-core-patient|6.1.0"]}},
    ])
    _write_ndjson(tmp_path / "Coverage.ndjson", [
        {"resourceType": "Coverage", "id": "cov1", "status": "active",
         "beneficiary": {"reference": "Patient/P1"}, "payor": [{"reference": "Patient/P1"}]},
    ])


class TestNativeHarness:
    def test_clean_dataset_passes_native(self, tmp_path):
        _valid_dataset(tmp_path)
        report = run_ig_validation(tmp_path, run_external=False)
        assert report.resources_scanned == 2
        assert report.native_ok
        assert report.ok  # external not run → does not block
        assert report.by_type["Patient"] == 1
        assert report.profiles["http://hl7.org/fhir/us/core/StructureDefinition/us-core-patient|6.1.0"] == 1

    def test_structural_invalid_detected(self, tmp_path):
        # Observation is missing its required `status` and `code` elements.
        _write_ndjson(tmp_path / "Observation.ndjson", [
            {"resourceType": "Observation", "id": "o1"},
        ])
        report = run_ig_validation(tmp_path, run_external=False)
        assert report.structural_invalid
        assert not report.native_ok
        assert not report.ok

    def test_dangling_ref_fails(self, tmp_path):
        _write_ndjson(tmp_path / "Coverage.ndjson", [
            {"resourceType": "Coverage", "id": "c1", "status": "active",
             "beneficiary": {"reference": "Patient/GONE"}},
        ])
        report = run_ig_validation(tmp_path, run_external=False)
        assert not report.ref_report.ok
        assert not report.ok

    def test_external_not_run_without_jar(self, tmp_path):
        _valid_dataset(tmp_path)
        report = run_ig_validation(tmp_path, validator_jar=None)
        # No jar in the test env → external does not run, and does not block.
        assert report.external.ran is False
        assert report.external.reason
        assert report.ok

    def test_report_renders(self, tmp_path):
        _valid_dataset(tmp_path)
        report = run_ig_validation(tmp_path, run_external=False)
        md = render_report(report, dataset=str(tmp_path))
        assert "IG conformance report — PASS" in md
        assert "Declared profiles" in md
        assert "us-core-patient" in md


class TestCli:
    def test_ig_writes_report_and_exits_zero(self, tmp_path):
        _valid_dataset(tmp_path)
        out = tmp_path / "report.md"
        result = runner.invoke(app, ["validate", str(tmp_path), "--ig", "--ig-report", str(out)])
        assert result.exit_code == 0, result.output
        assert out.exists()
        assert "IG conformance" in out.read_text()

    def test_ig_fails_on_structural_error(self, tmp_path):
        _write_ndjson(tmp_path / "Observation.ndjson", [
            {"resourceType": "Observation", "id": "o1"},  # missing status + code
        ])
        result = runner.invoke(app, ["validate", str(tmp_path), "--ig"])
        assert result.exit_code == 1

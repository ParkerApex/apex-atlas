"""Tests for the structural validator and `atlas validate` CLI command."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from parker_atlas.cli import app
from parker_atlas.validation.structural import (
    validate_file,
    validate_path,
)

runner = CliRunner()


def _write_generated_bundles(tmp_path, n: int = 3) -> None:
    result = runner.invoke(
        app, ["generate", "--patients", str(n), "--seed", "1", "--out", str(tmp_path)]
    )
    assert result.exit_code == 0, result.output


def _single_patient_bundle(tmp_path):
    files = [
        file
        for file in tmp_path.glob("*.json")
        if file.name != "generation-metadata.json"
    ]
    assert len(files) == 1
    return files[0]


class TestStructuralValidator:
    def test_validates_generated_bundles(self, tmp_path):
        _write_generated_bundles(tmp_path, 5)
        summary = validate_path(tmp_path)
        assert summary.total == 5
        assert summary.passed == 5
        assert summary.failed == 0
        assert summary.warnings == 0

    def test_flags_missing_identifier(self, tmp_path):
        _write_generated_bundles(tmp_path, 1)
        file = _single_patient_bundle(tmp_path)
        data = json.loads(file.read_text())
        data["entry"][0]["resource"]["identifier"] = []
        file.write_text(json.dumps(data))

        report = validate_file(file)
        assert not report.ok
        assert any("identifier" in e for e in report.errors)

    def test_flags_missing_gender(self, tmp_path):
        _write_generated_bundles(tmp_path, 1)
        file = _single_patient_bundle(tmp_path)
        data = json.loads(file.read_text())
        del data["entry"][0]["resource"]["gender"]
        file.write_text(json.dumps(data))

        report = validate_file(file)
        assert not report.ok
        assert any("gender" in e for e in report.errors)

    def test_flags_missing_family_name(self, tmp_path):
        _write_generated_bundles(tmp_path, 1)
        file = _single_patient_bundle(tmp_path)
        data = json.loads(file.read_text())
        data["entry"][0]["resource"]["name"][0].pop("family")
        file.write_text(json.dumps(data))

        report = validate_file(file)
        assert not report.ok
        assert any("family" in e for e in report.errors)

    def test_warns_on_missing_htest_tag(self, tmp_path):
        _write_generated_bundles(tmp_path, 1)
        file = _single_patient_bundle(tmp_path)
        data = json.loads(file.read_text())
        data["entry"][0]["resource"]["meta"]["tag"] = []
        file.write_text(json.dumps(data))

        report = validate_file(file)
        assert report.ok  # warning, not error
        assert any("HTEST" in w for w in report.warnings)

    def test_flags_invalid_json(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("{not valid json")
        report = validate_file(bad)
        assert not report.ok

    def test_flags_non_bundle_non_patient(self, tmp_path):
        other = tmp_path / "other.json"
        other.write_text(json.dumps({"resourceType": "Observation", "status": "final"}))
        report = validate_file(other)
        assert not report.ok


class TestValidateCLI:
    def test_validates_generated_output(self, tmp_path):
        out = tmp_path / "gen"
        gen = runner.invoke(
            app, ["generate", "--patients", "3", "--seed", "1", "--out", str(out)]
        )
        assert gen.exit_code == 0, gen.output

        result = runner.invoke(app, ["validate", str(out)])
        assert result.exit_code == 0
        assert "3 passed" in result.output
        assert "0 failed" in result.output

    def test_exits_nonzero_on_broken_file(self, tmp_path):
        _write_generated_bundles(tmp_path, 1)
        file = _single_patient_bundle(tmp_path)
        data = json.loads(file.read_text())
        data["entry"][0]["resource"]["identifier"] = []
        file.write_text(json.dumps(data))

        result = runner.invoke(app, ["validate", str(tmp_path)])
        assert result.exit_code == 1

    def test_strict_fails_on_warnings(self, tmp_path):
        _write_generated_bundles(tmp_path, 1)
        file = _single_patient_bundle(tmp_path)
        data = json.loads(file.read_text())
        data["entry"][0]["resource"]["meta"]["tag"] = []
        file.write_text(json.dumps(data))

        lax = runner.invoke(app, ["validate", str(tmp_path)])
        assert lax.exit_code == 0  # warning-only passes by default

        strict = runner.invoke(app, ["validate", str(tmp_path), "--strict"])
        assert strict.exit_code == 1

    def test_rejects_nonexistent_path(self, tmp_path):
        result = runner.invoke(app, ["validate", str(tmp_path / "missing")])
        assert result.exit_code == 1

    def test_exits_nonzero_when_no_json_files(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        result = runner.invoke(app, ["validate", str(empty)])
        assert result.exit_code == 1

    def test_verbose_shows_per_file_status(self, tmp_path):
        _write_generated_bundles(tmp_path, 2)
        result = runner.invoke(app, ["validate", str(tmp_path), "-v"])
        assert result.exit_code == 0
        assert "OK" in result.output

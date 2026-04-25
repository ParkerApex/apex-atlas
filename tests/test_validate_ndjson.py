"""Tests for `atlas validate` on NDJSON output."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from parker_atlas.cli import app
from parker_atlas.validation.structural import validate_file, validate_path

runner = CliRunner()


def _generate_ndjson(tmp_path, patients=10, module="hypertension", seed=42):
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


class TestNDJSONStructuralValidation:
    def test_validates_clean_ndjson_directory(self, tmp_path):
        _generate_ndjson(tmp_path)
        summary = validate_path(tmp_path)
        assert summary.total >= 1
        assert summary.failed == 0
        # Patient.ndjson is always present.
        assert any(f.path.name == "Patient.ndjson" for f in summary.files)

    def test_per_file_report_shows_one_file_per_resource_type(self, tmp_path):
        _generate_ndjson(tmp_path)
        summary = validate_path(tmp_path)
        rtypes = {f.path.stem for f in summary.files}
        assert "Patient" in rtypes
        # Hypertension module should produce these too at this seed/N.
        assert {"Condition", "Encounter", "Observation"}.issubset(rtypes)

    def test_flags_resourcetype_filename_mismatch(self, tmp_path):
        _generate_ndjson(tmp_path)
        # Corrupt Patient.ndjson by appending a Condition resource.
        patient_file = tmp_path / "Patient.ndjson"
        bad_resource = {
            "resourceType": "Condition",
            "subject": {"reference": "urn:uuid:fake"},
        }
        patient_file.write_text(
            patient_file.read_text() + json.dumps(bad_resource) + "\n"
        )
        report = validate_file(patient_file)
        assert not report.ok
        assert any("doesn't match filename" in e for e in report.errors)

    def test_flags_invalid_json_line(self, tmp_path):
        _generate_ndjson(tmp_path)
        patient_file = tmp_path / "Patient.ndjson"
        patient_file.write_text(patient_file.read_text() + "{not valid\n")
        report = validate_file(patient_file)
        assert not report.ok
        assert any("invalid JSON" in e for e in report.errors)

    def test_flags_schema_failure_per_line(self, tmp_path):
        _generate_ndjson(tmp_path)
        patient_file = tmp_path / "Patient.ndjson"
        # Inject a Patient with a malformed birthDate (FHIR rejects:
        # birthDate must match the FHIR date regex, not arbitrary strings).
        bad = {
            "resourceType": "Patient",
            "id": "bad",
            "birthDate": "not-a-date",
        }
        patient_file.write_text(patient_file.read_text() + json.dumps(bad) + "\n")
        report = validate_file(patient_file)
        assert not report.ok
        assert any("schema validation failed" in e for e in report.errors)

    def test_flags_us_core_minimums_per_line(self, tmp_path):
        # Hand-write a Patient.ndjson where the Patient has no identifier.
        patient_file = tmp_path / "Patient.ndjson"
        bad_patient = {
            "resourceType": "Patient",
            "name": [{"family": "Smith", "given": ["Jane"]}],
            "gender": "female",
        }
        patient_file.write_text(json.dumps(bad_patient) + "\n")
        report = validate_file(patient_file)
        assert not report.ok
        # US Core requires Patient.identifier ≥ 1.
        assert any("identifier" in e for e in report.errors)

    def test_warning_on_unexpected_filename(self, tmp_path):
        # A file named ImagingStudy.ndjson (Atlas doesn't produce this)
        # gets a warning rather than a hard error.
        path = tmp_path / "ImagingStudy.ndjson"
        path.write_text(json.dumps({"resourceType": "ImagingStudy"}) + "\n")
        report = validate_file(path)
        assert report.ok  # warning, not error
        assert any("not a recognized" in w for w in report.warnings)

    def test_empty_ndjson_file_warns(self, tmp_path):
        path = tmp_path / "Patient.ndjson"
        path.write_text("")
        report = validate_file(path)
        assert report.ok
        assert any("no data lines" in w for w in report.warnings)


class TestNDJSONCLI:
    def test_atlas_validate_works_on_ndjson_directory(self, tmp_path):
        _generate_ndjson(tmp_path)
        result = runner.invoke(app, ["validate", str(tmp_path)])
        assert result.exit_code == 0, result.output
        assert "passed" in result.output

    def test_atlas_validate_fails_on_corrupted_ndjson(self, tmp_path):
        _generate_ndjson(tmp_path)
        (tmp_path / "Patient.ndjson").write_text("{not valid json\n")
        result = runner.invoke(app, ["validate", str(tmp_path)])
        assert result.exit_code == 1

    def test_validates_mixed_directories(self, tmp_path):
        # Bundle JSON in one subdir, NDJSON in another — both should be
        # walked when validating the parent.
        bundles = tmp_path / "bundles"
        ndjson = tmp_path / "ndjson"
        for fmt, out in (("fhir-r4", bundles), ("ndjson", ndjson)):
            r = runner.invoke(
                app,
                [
                    "generate", "--patients", "3",
                    "--seed", "0", "--module", "hypertension",
                    "--format", fmt, "--out", str(out),
                ],
            )
            assert r.exit_code == 0, r.output
        result = runner.invoke(app, ["validate", str(tmp_path)])
        assert result.exit_code == 0, result.output

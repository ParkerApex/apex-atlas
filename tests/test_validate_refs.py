"""Tests for `atlas validate --refs` (referential integrity)."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from parker_atlas.cli import app
from parker_atlas.validation.references import validate_references

runner = CliRunner()


def _write_ndjson(path, rows):
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


class TestValidateReferences:
    def test_resolved_relative_refs(self, tmp_path):
        _write_ndjson(tmp_path / "Patient.ndjson", [{"resourceType": "Patient", "id": "P1"}])
        _write_ndjson(tmp_path / "Condition.ndjson", [
            {"resourceType": "Condition", "id": "c1", "subject": {"reference": "Patient/P1"}}
        ])
        report = validate_references(tmp_path)
        assert report.ok
        assert report.resolved == 1
        assert report.references_total == 1

    def test_dangling_relative_ref_detected(self, tmp_path):
        _write_ndjson(tmp_path / "Patient.ndjson", [{"resourceType": "Patient", "id": "P1"}])
        _write_ndjson(tmp_path / "Condition.ndjson", [
            {"resourceType": "Condition", "id": "c1", "subject": {"reference": "Patient/NOPE"}}
        ])
        report = validate_references(tmp_path)
        assert not report.ok
        assert len(report.dangling) == 1
        assert report.dangling[0].reference == "Patient/NOPE"

    def test_external_and_contained_refs_ignored(self, tmp_path):
        _write_ndjson(tmp_path / "Observation.ndjson", [
            {"resourceType": "Observation", "id": "o1",
             "subject": {"reference": "#contained"},
             "performer": [{"reference": "https://example.org/Practitioner/x"}]}
        ])
        report = validate_references(tmp_path)
        assert report.references_total == 0
        assert report.ok

    def test_bundle_fullurl_resolves(self, tmp_path):
        bundle = {
            "resourceType": "Bundle", "type": "transaction",
            "entry": [
                {"fullUrl": "urn:uuid:aaa", "resource": {"resourceType": "Patient", "id": "P1"}},
                {"fullUrl": "urn:uuid:bbb", "resource": {
                    "resourceType": "Condition", "id": "c1",
                    "subject": {"reference": "urn:uuid:aaa"}}},
            ],
        }
        (tmp_path / "b.json").write_text(json.dumps(bundle), encoding="utf-8")
        report = validate_references(tmp_path)
        assert report.ok
        assert report.resolved == 1

    def test_urn_uuid_ndjson_flagged(self, tmp_path):
        _write_ndjson(tmp_path / "Condition.ndjson", [
            {"resourceType": "Condition", "id": "c1", "subject": {"reference": "urn:uuid:zzz"}}
        ])
        report = validate_references(tmp_path)
        assert not report.ok
        assert report.urn_uuid_unresolved == 1

    def test_manifest_files_skipped(self, tmp_path):
        (tmp_path / "bulk-publish-manifest.json").write_text(
            json.dumps({"transactionTime": "t", "output": []}), encoding="utf-8"
        )
        _write_ndjson(tmp_path / "Patient.ndjson", [{"resourceType": "Patient", "id": "P1"}])
        report = validate_references(tmp_path)
        assert report.resources_scanned == 1


class TestCli:
    def test_cli_clean_exits_zero(self, tmp_path):
        _write_ndjson(tmp_path / "Patient.ndjson", [{"resourceType": "Patient", "id": "P1"}])
        _write_ndjson(tmp_path / "Coverage.ndjson", [
            {"resourceType": "Coverage", "id": "cov1", "beneficiary": {"reference": "Patient/P1"}}
        ])
        result = runner.invoke(app, ["validate", str(tmp_path), "--refs"])
        assert result.exit_code == 0, result.output
        assert "references resolved" in result.output

    def test_cli_dangling_exits_one(self, tmp_path):
        _write_ndjson(tmp_path / "Coverage.ndjson", [
            {"resourceType": "Coverage", "id": "cov1", "beneficiary": {"reference": "Patient/GONE"}}
        ])
        result = runner.invoke(app, ["validate", str(tmp_path), "--refs"])
        assert result.exit_code == 1

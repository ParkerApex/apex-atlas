"""Tests for `atlas generate --with-notes`."""

from __future__ import annotations

import base64
import json

import pytest
from typer.testing import CliRunner

from parker_atlas.cli import app

runner = CliRunner()


def _bundle_files(path):
    return sorted(
        p for p in path.glob("*.json") if p.name != "generation-metadata.json"
    )


def _generate(tmp_path, *, fmt: str = "fhir-r4", patients: int = 5, seed: int = 42, module: str = "hypertension", with_notes: bool = True):
    args = [
        "generate",
        "--patients", str(patients),
        "--seed", str(seed),
        "--module", module,
        "--format", fmt,
        "--out", str(tmp_path),
    ]
    if with_notes:
        args.append("--with-notes")
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    return result


class TestNotesInBundleOutput:
    def test_with_notes_emits_documentreference_per_fired_condition(self, tmp_path):
        _generate(tmp_path, patients=20, seed=42)
        # Across the 20-patient cohort, count fired Conditions vs notes — the
        # ratio should be 1:1 because we emit one progress note per condition.
        condition_count = 0
        doc_ref_count = 0
        for f in _bundle_files(tmp_path):
            data = json.loads(f.read_text())
            for entry in data["entry"]:
                rt = entry["resource"]["resourceType"]
                if rt == "Condition":
                    condition_count += 1
                elif rt == "DocumentReference":
                    doc_ref_count += 1
        assert condition_count > 0
        assert doc_ref_count == condition_count

    def test_without_with_notes_no_documentreference(self, tmp_path):
        _generate(tmp_path, patients=20, seed=42, with_notes=False)
        for f in _bundle_files(tmp_path):
            data = json.loads(f.read_text())
            for entry in data["entry"]:
                assert entry["resource"]["resourceType"] != "DocumentReference"

    def test_documentreference_links_back_to_encounter(self, tmp_path):
        _generate(tmp_path, patients=20, seed=42)
        # Hypertension module emits an Encounter per fired condition, so every
        # generated note should carry context.encounter.
        any_doc = False
        for f in _bundle_files(tmp_path):
            data = json.loads(f.read_text())
            for entry in data["entry"]:
                if entry["resource"]["resourceType"] == "DocumentReference":
                    any_doc = True
                    doc = entry["resource"]
                    assert "context" in doc
                    assert doc["context"]["encounter"][0]["reference"].startswith(
                        "urn:uuid:"
                    )
        assert any_doc, "expected at least one DocumentReference across cohort"

    def test_documentreference_contains_patient_demographics(self, tmp_path):
        _generate(tmp_path, patients=20, seed=42)
        # At least one note should round-trip cleanly and mention age + sex.
        decoded_any = False
        for f in _bundle_files(tmp_path):
            data = json.loads(f.read_text())
            for entry in data["entry"]:
                if entry["resource"]["resourceType"] == "DocumentReference":
                    body_b64 = entry["resource"]["content"][0]["attachment"]["data"]
                    body = base64.b64decode(body_b64).decode("utf-8")
                    assert "Progress Note" in body
                    assert "Patient:" in body
                    decoded_any = True
                    break
            if decoded_any:
                break
        assert decoded_any


class TestNotesInNDJSONOutput:
    def test_documentreference_ndjson_file_exists(self, tmp_path):
        _generate(tmp_path, fmt="ndjson", patients=20, seed=42)
        path = tmp_path / "DocumentReference.ndjson"
        assert path.exists()
        lines = [ln for ln in path.read_text().splitlines() if ln.strip()]
        # One note per fired Condition.
        cond_lines = [
            ln for ln in (tmp_path / "Condition.ndjson").read_text().splitlines()
            if ln.strip()
        ]
        assert len(lines) == len(cond_lines)


class TestNotesInParquetOutput:
    def test_documentreference_parquet_file_exists(self, tmp_path):
        pytest.importorskip("pyarrow")
        _generate(tmp_path, fmt="parquet", patients=20, seed=42)
        assert (tmp_path / "DocumentReference.parquet").exists()


class TestStructuralValidationAcceptsNotes:
    def test_validate_passes_on_cohort_with_notes(self, tmp_path):
        _generate(tmp_path, patients=10, seed=42)
        result = runner.invoke(app, ["validate", str(tmp_path)])
        assert result.exit_code == 0, result.output

    def test_validate_passes_on_ndjson_cohort_with_notes(self, tmp_path):
        _generate(tmp_path, fmt="ndjson", patients=10, seed=42)
        result = runner.invoke(app, ["validate", str(tmp_path)])
        assert result.exit_code == 0, result.output


class TestNoteReproducibility:
    def test_same_seed_produces_byte_identical_notes(self, tmp_path):
        a = tmp_path / "a"
        b = tmp_path / "b"
        for path in (a, b):
            r = runner.invoke(
                app,
                [
                    "generate", "--patients", "5",
                    "--seed", "7", "--module", "hypertension",
                    "--with-notes", "--out", str(path),
                ],
            )
            assert r.exit_code == 0, r.output
        for name in sorted(p.name for p in _bundle_files(a)):
            assert (a / name).read_text() == (b / name).read_text()

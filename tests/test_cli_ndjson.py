"""Tests for `atlas generate --format ndjson`."""

from __future__ import annotations

import json

import pytest
from fhir.resources.R4B.condition import Condition
from fhir.resources.R4B.encounter import Encounter
from fhir.resources.R4B.medicationrequest import MedicationRequest
from fhir.resources.R4B.observation import Observation
from fhir.resources.R4B.patient import Patient
from typer.testing import CliRunner

from parker_atlas.cli import app

runner = CliRunner()


_RESOURCE_CLASSES = {
    "Patient": Patient,
    "Condition": Condition,
    "Encounter": Encounter,
    "Observation": Observation,
    "MedicationRequest": MedicationRequest,
}


def _generate_ndjson(tmp_path, *, patients: int, seed: int = 0, module: str | None = None):
    args = [
        "generate",
        "--patients", str(patients),
        "--seed", str(seed),
        "--format", "ndjson",
        "--out", str(tmp_path),
    ]
    if module:
        args.extend(["--module", module])
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    return result


class TestNDJSONOutputShape:
    def test_writes_one_file_per_resource_type(self, tmp_path):
        _generate_ndjson(tmp_path, patients=10, module="hypertension")
        present = sorted(p.name for p in tmp_path.glob("*.ndjson"))
        # Patient is always present; the hypertension module emits the
        # other types when its conditions fire.
        assert "Patient.ndjson" in present
        # No JSON Bundle files in NDJSON mode.
        assert not list(tmp_path.glob("*.json"))

    def test_patient_file_has_one_line_per_patient(self, tmp_path):
        _generate_ndjson(tmp_path, patients=15)
        lines = (tmp_path / "Patient.ndjson").read_text().splitlines()
        assert len(lines) == 15

    def test_no_extra_resource_files_without_module(self, tmp_path):
        # Without --module, only Patients are emitted.
        _generate_ndjson(tmp_path, patients=5)
        rtypes = {p.stem for p in tmp_path.glob("*.ndjson")}
        assert rtypes == {"Patient"}

    def test_each_line_validates_against_fhir_model(self, tmp_path):
        _generate_ndjson(tmp_path, patients=20, module="hypertension")
        for f in tmp_path.glob("*.ndjson"):
            rtype = f.stem
            cls = _RESOURCE_CLASSES[rtype]
            for line in f.read_text().splitlines():
                if not line:
                    continue
                cls.model_validate(json.loads(line))

    def test_every_resource_in_file_matches_filename_type(self, tmp_path):
        _generate_ndjson(tmp_path, patients=20, module="hypertension")
        for f in tmp_path.glob("*.ndjson"):
            rtype = f.stem
            for line in f.read_text().splitlines():
                if not line:
                    continue
                obj = json.loads(line)
                assert obj["resourceType"] == rtype, (
                    f"{f.name}: expected resourceType={rtype}, got {obj['resourceType']}"
                )

    def test_lines_are_compact_no_indentation(self, tmp_path):
        # NDJSON requires one JSON object per line — compact (no newlines
        # inside the JSON). Verify no line in any file is empty mid-stream
        # and that each line parses as a single object.
        _generate_ndjson(tmp_path, patients=5, module="hypertension")
        for f in tmp_path.glob("*.ndjson"):
            text = f.read_text()
            assert text.endswith("\n"), f"{f.name} should end with newline"
            for line in text.splitlines():
                # Each line must be a complete JSON object.
                json.loads(line)


class TestNDJSONReproducibility:
    def test_same_seed_produces_byte_identical_files(self, tmp_path):
        a = tmp_path / "a"
        b = tmp_path / "b"
        for path in (a, b):
            r = runner.invoke(
                app,
                [
                    "generate",
                    "--patients", "5",
                    "--seed", "42",
                    "--module", "hypertension",
                    "--format", "ndjson",
                    "--out", str(path),
                ],
            )
            assert r.exit_code == 0, r.output
        files_a = sorted(p.name for p in a.glob("*.ndjson"))
        files_b = sorted(p.name for p in b.glob("*.ndjson"))
        assert files_a == files_b
        for name in files_a:
            assert (a / name).read_text() == (b / name).read_text()


class TestNDJSONCohortInteroperability:
    def test_bundles_from_ndjson_run_match_bundles_run(self, tmp_path):
        # Generate the same cohort in both formats, verify the underlying
        # resource counts agree (lines in NDJSON ↔ entries across Bundles).
        bundle_dir = tmp_path / "bundles"
        ndjson_dir = tmp_path / "ndjson"
        for fmt, out in (("fhir-r4", bundle_dir), ("ndjson", ndjson_dir)):
            r = runner.invoke(
                app,
                [
                    "generate",
                    "--patients", "20",
                    "--seed", "42",
                    "--module", "hypertension",
                    "--format", fmt,
                    "--out", str(out),
                ],
            )
            assert r.exit_code == 0, r.output

        # Count resources by type in the bundle output.
        bundle_counts: dict[str, int] = {}
        for f in bundle_dir.glob("*.json"):
            data = json.loads(f.read_text())
            for entry in data["entry"]:
                rt = entry["resource"]["resourceType"]
                bundle_counts[rt] = bundle_counts.get(rt, 0) + 1

        # Count resources by type in the NDJSON output.
        ndjson_counts: dict[str, int] = {}
        for f in ndjson_dir.glob("*.ndjson"):
            ndjson_counts[f.stem] = sum(1 for line in f.read_text().splitlines() if line)

        assert bundle_counts == ndjson_counts, (
            f"resource-count mismatch: bundles={bundle_counts}, ndjson={ndjson_counts}"
        )


class TestUnsupportedFormats:
    def test_parquet_still_rejected(self, tmp_path):
        r = runner.invoke(
            app,
            [
                "generate", "--patients", "1", "--seed", "0",
                "--format", "parquet",
                "--out", str(tmp_path),
            ],
        )
        assert r.exit_code == 2
        assert "not yet supported" in r.output

    def test_fhir_r5_still_rejected(self, tmp_path):
        r = runner.invoke(
            app,
            [
                "generate", "--patients", "1", "--seed", "0",
                "--format", "fhir-r5",
                "--out", str(tmp_path),
            ],
        )
        assert r.exit_code == 2
        assert "not yet supported" in r.output

"""Tests for `atlas generate --format parquet`."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from parker_atlas.cli import app

pa = pytest.importorskip("pyarrow")
pq = pytest.importorskip("pyarrow.parquet")

runner = CliRunner()


def _generate_parquet(tmp_path, *, patients: int, seed: int = 0, module: str | None = None):
    args = [
        "generate",
        "--patients", str(patients),
        "--seed", str(seed),
        "--format", "parquet",
        "--out", str(tmp_path),
    ]
    if module:
        args.extend(["--module", module])
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    return result


class TestParquetOutputShape:
    def test_writes_one_file_per_resource_type(self, tmp_path):
        _generate_parquet(tmp_path, patients=10, module="hypertension")
        present = sorted(p.name for p in tmp_path.glob("*.parquet"))
        assert "Patient.parquet" in present
        # No patient-bundle JSON or NDJSON in parquet mode. The
        # generation-metadata.json audit sidecar is written in every mode and
        # is not a resource file, so it doesn't count here.
        assert not [p for p in tmp_path.glob("*.json") if p.name != "generation-metadata.json"]
        assert not list(tmp_path.glob("*.ndjson"))

    def test_patient_file_has_one_row_per_patient(self, tmp_path):
        _generate_parquet(tmp_path, patients=15)
        table = pq.read_table(tmp_path / "Patient.parquet")
        assert table.num_rows == 15

    def test_no_extra_resource_files_without_module(self, tmp_path):
        _generate_parquet(tmp_path, patients=5)
        rtypes = {p.stem for p in tmp_path.glob("*.parquet")}
        assert rtypes == {"Patient"}

    def test_schema_has_id_subject_reference_raw_json(self, tmp_path):
        _generate_parquet(tmp_path, patients=5, module="hypertension")
        for f in tmp_path.glob("*.parquet"):
            table = pq.read_table(f)
            assert set(table.column_names) == {"id", "subject_reference", "raw_json"}

    def test_patient_subject_reference_is_null(self, tmp_path):
        _generate_parquet(tmp_path, patients=5)
        table = pq.read_table(tmp_path / "Patient.parquet")
        col = table.column("subject_reference").to_pylist()
        assert all(v is None for v in col)

    def test_non_patient_subject_references_resolve_to_patient_urn(self, tmp_path):
        _generate_parquet(tmp_path, patients=20, module="hypertension")
        # Build patient id set from Patient.parquet.
        pat = pq.read_table(tmp_path / "Patient.parquet")
        patient_ids = set(pat.column("id").to_pylist())
        for f in tmp_path.glob("*.parquet"):
            if f.stem == "Patient":
                continue
            tbl = pq.read_table(f)
            refs = tbl.column("subject_reference").to_pylist()
            for ref in refs:
                assert ref is not None and ref.startswith("urn:uuid:")
            # Each raw_json round-trips and matches the parquet typed columns.
            for raw in tbl.column("raw_json").to_pylist():
                obj = json.loads(raw)
                assert "resourceType" in obj
        # And patients have non-empty ids.
        assert all(pid for pid in patient_ids)

    def test_raw_json_round_trips_to_full_resource(self, tmp_path):
        _generate_parquet(tmp_path, patients=5, module="hypertension")
        for f in tmp_path.glob("*.parquet"):
            tbl = pq.read_table(f)
            for raw, typed_id in zip(
                tbl.column("raw_json").to_pylist(),
                tbl.column("id").to_pylist(),
            ):
                obj = json.loads(raw)
                assert obj["resourceType"] == f.stem
                # The typed id column matches the resource's id.
                assert obj.get("id") == typed_id


class TestParquetReproducibility:
    def test_same_seed_produces_same_row_counts(self, tmp_path):
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
                    "--format", "parquet",
                    "--out", str(path),
                ],
            )
            assert r.exit_code == 0, r.output
        files_a = sorted(p.name for p in a.glob("*.parquet"))
        files_b = sorted(p.name for p in b.glob("*.parquet"))
        assert files_a == files_b
        for name in files_a:
            ta = pq.read_table(a / name)
            tb = pq.read_table(b / name)
            assert ta.num_rows == tb.num_rows
            # raw_json columns should match line-for-line at the same seed.
            assert ta.column("raw_json").to_pylist() == tb.column("raw_json").to_pylist()


class TestParquetCrossFormat:
    def test_resource_counts_match_ndjson_run(self, tmp_path):
        # Generate the same cohort in both formats; count resources by type.
        ndjson_dir = tmp_path / "ndjson"
        parquet_dir = tmp_path / "parquet"
        for fmt, out in (("ndjson", ndjson_dir), ("parquet", parquet_dir)):
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

        ndjson_counts: dict[str, int] = {}
        for f in ndjson_dir.glob("*.ndjson"):
            ndjson_counts[f.stem] = sum(1 for line in f.read_text().splitlines() if line)
        parquet_counts: dict[str, int] = {}
        for f in parquet_dir.glob("*.parquet"):
            parquet_counts[f.stem] = pq.read_table(f).num_rows

        assert ndjson_counts == parquet_counts


class TestParquetCLI:
    def test_success_message_mentions_parquet(self, tmp_path):
        result = runner.invoke(
            app,
            [
                "generate",
                "--patients", "3",
                "--seed", "0",
                "--format", "parquet",
                "--out", str(tmp_path),
            ],
        )
        assert result.exit_code == 0, result.output
        assert "Parquet" in result.output
        assert "Patient.parquet" in result.output

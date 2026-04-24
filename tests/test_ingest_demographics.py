"""Tests for `atlas ingest demographics` and the underlying pipeline."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from parker_atlas.cli import app
from parker_atlas.ingest.demographics import ingest_demographics
from parker_atlas.ingest.prevalence import IngestionError

FIXTURES = Path(__file__).parent / "fixtures" / "ingest"
runner = CliRunner()


class TestDemographicsIngest:
    def test_round_trips_age_sex_fixture(self):
        table, csv_content, prov_yaml = ingest_demographics(
            FIXTURES / "age_sex.csv", FIXTURES / "age_sex_meta.yaml"
        )
        assert table == "age_sex"
        header = csv_content.splitlines()[0]
        assert header == "age_low,age_high,sex,weight"
        # Provenance carries the citation chain.
        meta = yaml.safe_load(prov_yaml)
        assert meta["source"]["provenance"] == "sourced"
        assert meta["source"]["citations"]

    def test_rejects_placeholder_provenance(self, tmp_path):
        meta_path = tmp_path / "meta.yaml"
        meta_path.write_text(
            "table: age_sex\nsource: {provenance: placeholder}\n"
        )
        with pytest.raises(IngestionError, match="provenance"):
            ingest_demographics(FIXTURES / "age_sex.csv", meta_path)

    def test_rejects_unknown_table(self, tmp_path):
        meta_path = tmp_path / "meta.yaml"
        meta_path.write_text(
            "table: age_gender_magic\nsource: {provenance: sourced}\n"
        )
        with pytest.raises(IngestionError, match="unknown table"):
            ingest_demographics(FIXTURES / "age_sex.csv", meta_path)

    def test_rejects_missing_csv_columns(self, tmp_path):
        bad_csv = tmp_path / "bad.csv"
        bad_csv.write_text("age_low,sex,weight\n0,female,0.5\n")
        with pytest.raises(IngestionError, match="missing required columns"):
            ingest_demographics(bad_csv, FIXTURES / "age_sex_meta.yaml")

    def test_rejects_invalid_sex(self, tmp_path):
        bad_csv = tmp_path / "bad.csv"
        bad_csv.write_text(
            "age_low,age_high,sex,weight\n0,17,aliens,0.5\n"
        )
        with pytest.raises(IngestionError, match="sex must be"):
            ingest_demographics(bad_csv, FIXTURES / "age_sex_meta.yaml")

    def test_rejects_invalid_age_range(self, tmp_path):
        bad_csv = tmp_path / "bad.csv"
        bad_csv.write_text(
            "age_low,age_high,sex,weight\n50,20,female,0.5\n"
        )
        with pytest.raises(IngestionError, match="invalid age range"):
            ingest_demographics(bad_csv, FIXTURES / "age_sex_meta.yaml")

    def test_rejects_non_positive_weight(self, tmp_path):
        bad_csv = tmp_path / "bad.csv"
        bad_csv.write_text(
            "age_low,age_high,sex,weight\n0,17,female,0\n"
        )
        with pytest.raises(IngestionError, match="weight must be positive"):
            ingest_demographics(bad_csv, FIXTURES / "age_sex_meta.yaml")

    def test_race_table_validates(self, tmp_path):
        csv_path = tmp_path / "race.csv"
        csv_path.write_text(
            "code,display,weight\n"
            "2106-3,White,0.59\n"
            "2054-5,Black or African American,0.13\n"
        )
        meta_path = tmp_path / "meta.yaml"
        meta_path.write_text(
            "table: race\nsource: {provenance: sourced, name: fixture}\n"
        )
        table, csv_content, _ = ingest_demographics(csv_path, meta_path)
        assert table == "race"
        assert "2106-3" in csv_content


class TestDemographicsCLI:
    def test_writes_csv_and_provenance_sidecar(self, tmp_path):
        out = tmp_path / "age_sex.csv"
        result = runner.invoke(
            app,
            [
                "ingest", "demographics",
                "-i", str(FIXTURES / "age_sex.csv"),
                "-m", str(FIXTURES / "age_sex_meta.yaml"),
                "-o", str(out),
            ],
        )
        assert result.exit_code == 0, result.output
        assert out.exists()
        sidecar = out.with_suffix(".provenance.yaml")
        assert sidecar.exists()
        assert "provenance: sourced" in sidecar.read_text()

    def test_refuses_overwrite_without_flag(self, tmp_path):
        out = tmp_path / "age_sex.csv"
        out.write_text("pre-existing")
        result = runner.invoke(
            app,
            [
                "ingest", "demographics",
                "-i", str(FIXTURES / "age_sex.csv"),
                "-m", str(FIXTURES / "age_sex_meta.yaml"),
                "-o", str(out),
            ],
        )
        assert result.exit_code == 1
        assert "already exist" in result.output

    def test_overwrite_flag_replaces_both(self, tmp_path):
        out = tmp_path / "age_sex.csv"
        sidecar = out.with_suffix(".provenance.yaml")
        out.write_text("old")
        sidecar.write_text("old")
        result = runner.invoke(
            app,
            [
                "ingest", "demographics",
                "-i", str(FIXTURES / "age_sex.csv"),
                "-m", str(FIXTURES / "age_sex_meta.yaml"),
                "-o", str(out),
                "--overwrite",
            ],
        )
        assert result.exit_code == 0, result.output
        assert "age_low" in out.read_text()
        assert "provenance: sourced" in sidecar.read_text()

    def test_missing_input_exits_cleanly(self, tmp_path):
        result = runner.invoke(
            app,
            [
                "ingest", "demographics",
                "-i", str(tmp_path / "no.csv"),
                "-m", str(FIXTURES / "age_sex_meta.yaml"),
                "-o", str(tmp_path / "out.csv"),
            ],
        )
        assert result.exit_code == 1

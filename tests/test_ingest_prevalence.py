"""Tests for `atlas ingest prevalence` and the underlying ingest pipeline."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from parker_atlas.cli import app
from parker_atlas.ingest.prevalence import IngestionError, ingest_prevalence
from parker_atlas.validation.expectations import load_expectation_from_str

FIXTURES = Path(__file__).parent / "fixtures" / "ingest"
runner = CliRunner()


class TestPrevalenceIngest:
    def test_ingests_age_bracket_csv(self):
        rendered = ingest_prevalence(
            FIXTURES / "hypertension_targets.csv",
            FIXTURES / "hypertension_meta.yaml",
        )
        # Output should round-trip through the expectation loader.
        exp = load_expectation_from_str(rendered)
        assert exp.module == "hypertension"
        assert exp.source.provenance == "sourced"
        assert len(exp.metrics) == 1
        m = exp.metrics[0]
        assert m.stratify_by == "age_bracket"
        assert m.condition_code == "59621000"
        assert m.targets[(18, 34)] == 0.22
        assert m.targets[(75, 95)] == 0.80

    def test_ingests_sex_stratified_csv(self):
        rendered = ingest_prevalence(
            FIXTURES / "hypertension_sex_stratified.csv",
            FIXTURES / "hypertension_sex_meta.yaml",
        )
        exp = load_expectation_from_str(rendered)
        assert len(exp.metrics) == 1
        m = exp.metrics[0]
        assert m.stratify_by == "sex_and_age"
        assert m.targets_by_sex is not None
        assert m.targets_by_sex["female"][(35, 54)] == 0.45
        assert m.targets_by_sex["male"][(35, 54)] == 0.49

    def test_preserves_citations(self):
        rendered = ingest_prevalence(
            FIXTURES / "hypertension_targets.csv",
            FIXTURES / "hypertension_meta.yaml",
        )
        data = yaml.safe_load(rendered)
        citations = data["source"]["citations"]
        assert len(citations) == 1
        assert citations[0]["source"] == "APEX Atlas test fixture"

    def test_rejects_placeholder_provenance(self, tmp_path):
        bad_meta = tmp_path / "meta.yaml"
        bad_meta.write_text(
            "module: t\n"
            "source: {provenance: placeholder}\n"
            "tolerance: {kind: wilson, confidence: 95}\n"
            "metrics:\n"
            "  m: {condition_code: x, condition_system: y}\n"
        )
        csv_path = tmp_path / "data.csv"
        csv_path.write_text("metric_id,bracket,prevalence\nm,0-99,0.5\n")
        with pytest.raises(IngestionError, match="provenance"):
            ingest_prevalence(csv_path, bad_meta)

    def test_rejects_missing_csv_columns(self, tmp_path):
        csv_path = tmp_path / "bad.csv"
        csv_path.write_text("metric_id,prevalence\nm,0.5\n")
        with pytest.raises(IngestionError, match="missing required columns"):
            ingest_prevalence(csv_path, FIXTURES / "hypertension_meta.yaml")

    def test_rejects_mixed_sex_within_metric(self, tmp_path):
        csv_path = tmp_path / "mixed.csv"
        csv_path.write_text(
            "metric_id,bracket,sex,prevalence\n"
            "essential_hypertension,0-99,female,0.5\n"
            "essential_hypertension,0-99,,0.5\n"
        )
        with pytest.raises(IngestionError, match="some rows have sex"):
            ingest_prevalence(csv_path, FIXTURES / "hypertension_meta.yaml")

    def test_rejects_unknown_sex_value(self, tmp_path):
        csv_path = tmp_path / "bad_sex.csv"
        csv_path.write_text(
            "metric_id,bracket,sex,prevalence\n"
            "essential_hypertension,0-99,other,0.5\n"
        )
        with pytest.raises(IngestionError, match="invalid sex values"):
            ingest_prevalence(csv_path, FIXTURES / "hypertension_meta.yaml")

    def test_rejects_metadata_missing_metric(self, tmp_path):
        csv_path = tmp_path / "data.csv"
        csv_path.write_text(
            "metric_id,bracket,prevalence\n"
            "undeclared_metric,0-99,0.5\n"
        )
        with pytest.raises(IngestionError, match="missing entry for metric"):
            ingest_prevalence(csv_path, FIXTURES / "hypertension_meta.yaml")

    def test_rejects_empty_csv(self, tmp_path):
        csv_path = tmp_path / "empty.csv"
        csv_path.write_text("metric_id,bracket,prevalence\n")
        with pytest.raises(IngestionError, match="no data rows"):
            ingest_prevalence(csv_path, FIXTURES / "hypertension_meta.yaml")

    def test_rejects_malformed_metadata(self, tmp_path):
        bad = tmp_path / "meta.yaml"
        bad.write_text("module: t\n")  # missing source, tolerance, metrics
        with pytest.raises(IngestionError, match="required key"):
            ingest_prevalence(FIXTURES / "hypertension_targets.csv", bad)

    def test_output_roundtrips_via_loader(self):
        rendered = ingest_prevalence(
            FIXTURES / "hypertension_targets.csv",
            FIXTURES / "hypertension_meta.yaml",
        )
        # If the rendered YAML is malformed, load_expectation_from_str raises.
        exp = load_expectation_from_str(rendered)
        assert exp is not None


class TestPrevalenceCLI:
    def test_stdout_by_default(self):
        result = runner.invoke(
            app,
            [
                "ingest", "prevalence",
                "-i", str(FIXTURES / "hypertension_targets.csv"),
                "-m", str(FIXTURES / "hypertension_meta.yaml"),
            ],
        )
        assert result.exit_code == 0, result.output
        assert "module: hypertension" in result.output
        assert "provenance: sourced" in result.output

    def test_writes_to_output_path(self, tmp_path):
        out = tmp_path / "generated.yaml"
        result = runner.invoke(
            app,
            [
                "ingest", "prevalence",
                "-i", str(FIXTURES / "hypertension_targets.csv"),
                "-m", str(FIXTURES / "hypertension_meta.yaml"),
                "-o", str(out),
            ],
        )
        assert result.exit_code == 0, result.output
        assert out.exists()
        load_expectation_from_str(out.read_text())

    def test_refuses_overwrite_without_flag(self, tmp_path):
        out = tmp_path / "existing.yaml"
        out.write_text("placeholder")
        result = runner.invoke(
            app,
            [
                "ingest", "prevalence",
                "-i", str(FIXTURES / "hypertension_targets.csv"),
                "-m", str(FIXTURES / "hypertension_meta.yaml"),
                "-o", str(out),
            ],
        )
        assert result.exit_code == 1
        assert "already exists" in result.output

    def test_overwrite_flag_allows_replacement(self, tmp_path):
        out = tmp_path / "existing.yaml"
        out.write_text("placeholder")
        result = runner.invoke(
            app,
            [
                "ingest", "prevalence",
                "-i", str(FIXTURES / "hypertension_targets.csv"),
                "-m", str(FIXTURES / "hypertension_meta.yaml"),
                "-o", str(out),
                "--overwrite",
            ],
        )
        assert result.exit_code == 0, result.output
        assert "module: hypertension" in out.read_text()

    def test_missing_input_exits_cleanly(self, tmp_path):
        result = runner.invoke(
            app,
            [
                "ingest", "prevalence",
                "-i", str(tmp_path / "does-not-exist.csv"),
                "-m", str(FIXTURES / "hypertension_meta.yaml"),
            ],
        )
        assert result.exit_code == 1
        assert "does not exist" in result.output

    def test_reports_ingest_errors(self, tmp_path):
        # Fixtures with placeholder provenance → ingest refuses.
        bad_meta = tmp_path / "meta.yaml"
        bad_meta.write_text(
            "module: t\n"
            "source: {provenance: placeholder}\n"
            "tolerance: {kind: wilson, confidence: 95}\n"
            "metrics:\n"
            "  m: {condition_code: x, condition_system: y}\n"
        )
        csv_path = tmp_path / "data.csv"
        csv_path.write_text("metric_id,bracket,prevalence\nm,0-99,0.5\n")

        result = runner.invoke(
            app,
            [
                "ingest", "prevalence",
                "-i", str(csv_path),
                "-m", str(bad_meta),
            ],
        )
        assert result.exit_code == 1
        assert "provenance" in result.output

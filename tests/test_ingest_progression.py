"""Tests for `atlas ingest progression`.

The ingest reads a CSV of (from, to, after_years, probability) plus a
metadata YAML, and writes a progressions-overlay YAML that the runtime
loader applies on top of the matching bundled module. The output is
round-tripped through `apply_progressions_overlay` against the bundled
module so structural mismatches fail at ingest time.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from parker_atlas.cli import app
from parker_atlas.ingest.progression import IngestionError, ingest_progression

runner = CliRunner()


def _write(p: Path, text: str) -> Path:
    p.write_text(text, encoding="utf-8")
    return p


def _hypertension_csv() -> str:
    return (
        "from,to,after_years,probability,source_note\n"
        "essential_hypertension,hypertensive_ckd,10,0.105,KDIGO 2024 + USRDS 2023 ADR\n"
    )


def _hypertension_metadata() -> str:
    return """
module: hypertension
version: 1.0.0
source:
  name: KDIGO 2024 CKD Guideline + USRDS 2023 ADR
  provenance: sourced
  url: https://kdigo.org/guidelines/ckd-evaluation-and-management/
  citations:
    - source: KDIGO 2024 Clinical Practice Guideline for the Evaluation and Management of CKD
      url: https://kdigo.org/guidelines/ckd-evaluation-and-management/
      version: KDIGO 2024
      accessed: '2026-04-25'
"""


class TestIngestProgressionHappyPath:
    def test_round_trips_to_valid_overlay(self, tmp_path):
        csv = _write(tmp_path / "in.csv", _hypertension_csv())
        meta = _write(tmp_path / "meta.yaml", _hypertension_metadata())
        rendered = ingest_progression(csv, meta)
        parsed = yaml.safe_load(rendered)
        assert parsed["module"] == "hypertension"
        assert parsed["source"]["provenance"] == "sourced"
        assert parsed["progressions"] == [
            {
                "from": "essential_hypertension",
                "to": "hypertensive_ckd",
                "after_years": 10,
                "probability": 0.105,
            }
        ]

    def test_includes_full_citation_chain(self, tmp_path):
        csv = _write(tmp_path / "in.csv", _hypertension_csv())
        meta = _write(tmp_path / "meta.yaml", _hypertension_metadata())
        rendered = ingest_progression(csv, meta)
        parsed = yaml.safe_load(rendered)
        cites = parsed["source"]["citations"]
        assert len(cites) == 1
        assert cites[0]["url"].startswith("https://kdigo.org/")


class TestIngestProgressionValidation:
    def test_rejects_placeholder_provenance(self, tmp_path):
        csv = _write(tmp_path / "in.csv", _hypertension_csv())
        bad_meta = _hypertension_metadata().replace("provenance: sourced", "provenance: placeholder")
        meta = _write(tmp_path / "meta.yaml", bad_meta)
        with pytest.raises(IngestionError, match="provenance of 'sourced' or 'verified'"):
            ingest_progression(csv, meta)

    def test_rejects_unknown_progression_pair(self, tmp_path):
        # Module hypertension declares (essential_hypertension, hypertensive_ckd).
        # Try to override (essential_hypertension, ghost) — should fail at the
        # round-trip step.
        bad_csv = (
            "from,to,after_years,probability\n"
            "essential_hypertension,ghost_condition,10,0.10\n"
        )
        csv = _write(tmp_path / "in.csv", bad_csv)
        meta = _write(tmp_path / "meta.yaml", _hypertension_metadata())
        with pytest.raises(IngestionError, match="not present in module"):
            ingest_progression(csv, meta)

    def test_rejects_missing_csv_columns(self, tmp_path):
        bad_csv = "from,to,probability\nessential_hypertension,hypertensive_ckd,0.10\n"
        csv = _write(tmp_path / "in.csv", bad_csv)
        meta = _write(tmp_path / "meta.yaml", _hypertension_metadata())
        with pytest.raises(IngestionError, match="missing required columns"):
            ingest_progression(csv, meta)

    def test_rejects_probability_out_of_range(self, tmp_path):
        bad_csv = (
            "from,to,after_years,probability\n"
            "essential_hypertension,hypertensive_ckd,10,1.5\n"
        )
        csv = _write(tmp_path / "in.csv", bad_csv)
        meta = _write(tmp_path / "meta.yaml", _hypertension_metadata())
        with pytest.raises(IngestionError, match="probability"):
            ingest_progression(csv, meta)

    def test_rejects_non_integer_after_years(self, tmp_path):
        bad_csv = (
            "from,to,after_years,probability\n"
            "essential_hypertension,hypertensive_ckd,not-a-number,0.10\n"
        )
        csv = _write(tmp_path / "in.csv", bad_csv)
        meta = _write(tmp_path / "meta.yaml", _hypertension_metadata())
        with pytest.raises(IngestionError, match="after_years must be an integer"):
            ingest_progression(csv, meta)

    def test_rejects_duplicate_pair(self, tmp_path):
        bad_csv = (
            "from,to,after_years,probability\n"
            "essential_hypertension,hypertensive_ckd,10,0.10\n"
            "essential_hypertension,hypertensive_ckd,12,0.15\n"
        )
        csv = _write(tmp_path / "in.csv", bad_csv)
        meta = _write(tmp_path / "meta.yaml", _hypertension_metadata())
        with pytest.raises(IngestionError, match="duplicate"):
            ingest_progression(csv, meta)

    def test_rejects_missing_metadata_module(self, tmp_path):
        bad_meta = """
version: 1.0.0
source:
  name: x
  provenance: sourced
"""
        csv = _write(tmp_path / "in.csv", _hypertension_csv())
        meta = _write(tmp_path / "meta.yaml", bad_meta)
        with pytest.raises(IngestionError, match="missing required key: module"):
            ingest_progression(csv, meta)

    def test_rejects_unknown_target_module(self, tmp_path):
        bad_meta = _hypertension_metadata().replace(
            "module: hypertension", "module: not_a_real_module"
        )
        csv = _write(tmp_path / "in.csv", _hypertension_csv())
        meta = _write(tmp_path / "meta.yaml", bad_meta)
        with pytest.raises(IngestionError, match="cannot validate overlay"):
            ingest_progression(csv, meta)


class TestIngestProgressionCLI:
    def test_writes_overlay_to_disk(self, tmp_path):
        csv = _write(tmp_path / "in.csv", _hypertension_csv())
        meta = _write(tmp_path / "meta.yaml", _hypertension_metadata())
        out = tmp_path / "hypertension.progressions.yaml"
        result = runner.invoke(
            app,
            [
                "ingest", "progression",
                "-i", str(csv),
                "-m", str(meta),
                "-o", str(out),
            ],
        )
        assert result.exit_code == 0, result.output
        assert out.exists()
        parsed = yaml.safe_load(out.read_text())
        assert parsed["module"] == "hypertension"

    def test_prints_to_stdout_without_output_flag(self, tmp_path):
        csv = _write(tmp_path / "in.csv", _hypertension_csv())
        meta = _write(tmp_path / "meta.yaml", _hypertension_metadata())
        result = runner.invoke(
            app,
            [
                "ingest", "progression",
                "-i", str(csv),
                "-m", str(meta),
            ],
        )
        assert result.exit_code == 0
        assert "module: hypertension" in result.output

    def test_refuses_overwrite_without_flag(self, tmp_path):
        csv = _write(tmp_path / "in.csv", _hypertension_csv())
        meta = _write(tmp_path / "meta.yaml", _hypertension_metadata())
        out = tmp_path / "hypertension.progressions.yaml"
        out.write_text("existing")
        result = runner.invoke(
            app,
            [
                "ingest", "progression",
                "-i", str(csv),
                "-m", str(meta),
                "-o", str(out),
            ],
        )
        assert result.exit_code == 1
        # Rich may line-wrap the error message; collapse whitespace.
        assert "already" in result.output and "exists" in result.output

    def test_overwrite_flag_replaces_file(self, tmp_path):
        csv = _write(tmp_path / "in.csv", _hypertension_csv())
        meta = _write(tmp_path / "meta.yaml", _hypertension_metadata())
        out = tmp_path / "hypertension.progressions.yaml"
        out.write_text("existing")
        result = runner.invoke(
            app,
            [
                "ingest", "progression",
                "-i", str(csv),
                "-m", str(meta),
                "-o", str(out),
                "--overwrite",
            ],
        )
        assert result.exit_code == 0
        assert "module: hypertension" in out.read_text()

    def test_missing_input_csv_fails_cleanly(self, tmp_path):
        meta = _write(tmp_path / "meta.yaml", _hypertension_metadata())
        result = runner.invoke(
            app,
            [
                "ingest", "progression",
                "-i", str(tmp_path / "nope.csv"),
                "-m", str(meta),
            ],
        )
        assert result.exit_code == 1
        assert "input CSV does not exist" in result.output

    def test_ingest_failure_surfaces_message(self, tmp_path):
        bad_csv = (
            "from,to,after_years,probability\n"
            "essential_hypertension,ghost,10,0.10\n"
        )
        csv = _write(tmp_path / "in.csv", bad_csv)
        meta = _write(tmp_path / "meta.yaml", _hypertension_metadata())
        result = runner.invoke(
            app,
            [
                "ingest", "progression",
                "-i", str(csv),
                "-m", str(meta),
            ],
        )
        assert result.exit_code == 1
        assert "ingest failed" in result.output

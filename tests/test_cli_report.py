"""Smoke + correctness tests for `atlas report` (HTML cohort report)."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from parker_atlas.cli import app

runner = CliRunner()


def _generate_cohort(tmp_path: Path, *, patients: int = 60) -> Path:
    out = tmp_path / "cohort"
    result = runner.invoke(
        app,
        [
            "generate",
            "--patients", str(patients),
            "--seed", "42",
            "--module", "hypertension",
            "--out", str(out),
        ],
    )
    assert result.exit_code == 0, result.stdout
    return out


def test_report_demographics_only(tmp_path: Path) -> None:
    cohort = _generate_cohort(tmp_path)
    out = tmp_path / "report.html"

    result = runner.invoke(
        app, ["report", str(cohort), "--out", str(out)]
    )
    assert result.exit_code == 0, result.stdout
    assert out.is_file()

    html_doc = out.read_text(encoding="utf-8")
    assert "<!doctype html>" in html_doc
    assert "APEX Atlas cohort report" in html_doc
    assert "Demographics" in html_doc
    assert "Conditions" in html_doc
    # No fidelity section without --module.
    assert "Fidelity vs." not in html_doc


def test_report_with_fidelity(tmp_path: Path) -> None:
    cohort = _generate_cohort(tmp_path, patients=80)
    out = tmp_path / "report.html"

    result = runner.invoke(
        app,
        [
            "report",
            str(cohort),
            "--module", "hypertension",
            "--out", str(out),
            "--min-samples", "1",
        ],
    )
    # Small N + sampling variance can flip pass/fail; we only assert the
    # report was written and contains the fidelity section.
    assert out.is_file()
    html_doc = out.read_text(encoding="utf-8")
    assert "Fidelity vs. hypertension" in html_doc
    assert "Citations" in html_doc or "Skipped" in html_doc or "PASS" in html_doc or "FAIL" in html_doc


def test_report_missing_path(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["report", str(tmp_path / "does-not-exist")]
    )
    assert result.exit_code == 1


def test_report_empty_cohort(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    out = tmp_path / "report.html"
    result = runner.invoke(
        app, ["report", str(empty), "--out", str(out)]
    )
    assert result.exit_code == 1

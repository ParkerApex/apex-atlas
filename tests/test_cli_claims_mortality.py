"""End-to-end coverage for claims/EOBs and module mortality hooks."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from parker_atlas.cli import app

runner = CliRunner()


def _bundles(out_dir: Path) -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted(out_dir.glob("*.json"))]


def test_generate_with_claims_requires_coverage(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["generate", "--patients", "1", "--with-claims", "--out", str(tmp_path)],
    )
    assert result.exit_code == 1
    assert "requires --with-coverage" in result.output


def test_generate_with_claims_emits_claim_and_eob_per_encounter(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "generate",
            "--patients", "20",
            "--seed", "42",
            "--module", "hypertension",
            "--with-coverage",
            "--with-claims",
            "--out", str(tmp_path),
        ],
    )
    assert result.exit_code == 0, result.output

    seen = False
    for bundle in _bundles(tmp_path):
        resources = [entry["resource"] for entry in bundle["entry"]]
        encounters = [r for r in resources if r["resourceType"] == "Encounter"]
        claims = [r for r in resources if r["resourceType"] == "Claim"]
        eobs = [r for r in resources if r["resourceType"] == "ExplanationOfBenefit"]
        has_coverage = any(r["resourceType"] == "Coverage" for r in resources)
        if encounters and has_coverage:
            seen = True
            assert len(claims) == len(encounters)
            assert len(eobs) == len(encounters)
    assert seen


def test_stroke_mortality_marks_patient_and_emits_cause_of_death(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "generate",
            "--patients", "2000",
            "--seed", "42",
            "--module", "stroke",
            "--out", str(tmp_path),
        ],
    )
    assert result.exit_code == 0, result.output

    deceased = 0
    for bundle in _bundles(tmp_path):
        resources = [entry["resource"] for entry in bundle["entry"]]
        patient = next(r for r in resources if r["resourceType"] == "Patient")
        if "deceasedDateTime" not in patient:
            continue
        deceased += 1
        assert any(
            r["resourceType"] == "Observation"
            and r["code"]["coding"][0]["code"] == "69453-9"
            for r in resources
        )
    assert deceased > 0

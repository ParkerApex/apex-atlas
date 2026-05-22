"""End-to-end CLI test for --with-coverage."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from parker_atlas.cli import app

runner = CliRunner()


def _bundles(out_dir: Path) -> list[dict]:
    return [
        json.loads(p.read_text())
        for p in sorted(out_dir.glob("*.json"))
        if p.name != "generation-metadata.json"
    ]


def test_generate_with_coverage_emits_coverage_payer_org_and_plan(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "generate",
            "--patients", "20",
            "--seed", "42",
            "--with-coverage",
            "--out", str(tmp_path),
        ],
    )
    assert result.exit_code == 0, result.output

    bundles = _bundles(tmp_path)
    assert len(bundles) == 20

    # Most patients should carry a Coverage (uninsured patients won't),
    # and every Coverage must come with a payer Organization and an
    # InsurancePlan in the same Bundle.
    coverage_count = 0
    for b in bundles:
        rtypes = [e["resource"]["resourceType"] for e in b["entry"]]
        if "Coverage" in rtypes:
            coverage_count += 1
            assert "Organization" in rtypes
            assert "InsurancePlan" in rtypes
            cov = next(e["resource"] for e in b["entry"] if e["resource"]["resourceType"] == "Coverage")
            assert cov["beneficiary"]["reference"].startswith("urn:uuid:")
            # payor reference must resolve to the Organization fullUrl in the same Bundle
            payer_org_url = next(
                e["fullUrl"]
                for e in b["entry"]
                if e["resource"]["resourceType"] == "Organization"
            )
            assert cov["payor"][0]["reference"] == payer_org_url
    assert coverage_count >= 15  # most of 20 covered


def test_without_with_coverage_no_coverage_resources(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "generate",
            "--patients", "5",
            "--seed", "42",
            "--out", str(tmp_path),
        ],
    )
    assert result.exit_code == 0, result.output
    for b in _bundles(tmp_path):
        rtypes = [e["resource"]["resourceType"] for e in b["entry"]]
        assert "Coverage" not in rtypes
        assert "InsurancePlan" not in rtypes

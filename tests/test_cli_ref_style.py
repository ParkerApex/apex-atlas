"""Tests for `atlas generate --ref-style` (NDJSON reference style)."""

from __future__ import annotations

import json

from fhir.resources.R4B.condition import Condition
from fhir.resources.R4B.coverage import Coverage
from typer.testing import CliRunner

from parker_atlas.cli import app

runner = CliRunner()


def _gen(tmp_path, *args):
    r = runner.invoke(
        app,
        ["generate", "--patients", "40", "--seed", "5", "--as-of", "2026-04-25",
         "--format", "ndjson", "--module", "hypertension,diabetes",
         "--with-coverage", "--out", str(tmp_path), *args],
    )
    assert r.exit_code == 0, r.output
    return r


class TestRelativeRefs:
    def test_relative_emits_resource_id_references(self, tmp_path):
        _gen(tmp_path, "--ref-style", "relative")
        cond = json.loads((tmp_path / "Condition.ndjson").read_text().splitlines()[0])
        Condition(**cond)
        assert cond["subject"]["reference"].startswith("Patient/GPX-SYN-")

        cov = json.loads((tmp_path / "Coverage.ndjson").read_text().splitlines()[0])
        Coverage(**cov)
        assert cov["beneficiary"]["reference"].startswith("Patient/GPX-SYN-")
        assert cov["payor"][0]["reference"].startswith("Organization/")

    def test_relative_has_no_urn_uuid(self, tmp_path):
        _gen(tmp_path, "--ref-style", "relative")
        for f in tmp_path.glob("*.ndjson"):
            assert "urn:uuid" not in f.read_text(), f.name

    def test_default_is_urn_uuid(self, tmp_path):
        _gen(tmp_path)  # default ref style
        cond = json.loads((tmp_path / "Condition.ndjson").read_text().splitlines()[0])
        assert cond["subject"]["reference"].startswith("urn:uuid:")

    def test_ref_style_in_metadata(self, tmp_path):
        _gen(tmp_path, "--ref-style", "relative")
        meta = json.loads((tmp_path / "generation-metadata.json").read_text())
        assert meta["ref_style"] == "relative"

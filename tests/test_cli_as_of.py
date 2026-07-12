"""Tests for `atlas generate --as-of` (date-pinned reproducibility)."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from parker_atlas.cli import app

runner = CliRunner()


def _gen(tmp_path, *args):
    return runner.invoke(
        app,
        ["generate", "--patients", "25", "--seed", "3", "--format", "ndjson",
         "--module", "hypertension", "--out", str(tmp_path), *args],
    )


class TestAsOf:
    def test_same_seed_and_as_of_is_byte_identical(self, tmp_path):
        a, b = tmp_path / "a", tmp_path / "b"
        assert _gen(a, "--as-of", "2026-04-25").exit_code == 0
        assert _gen(b, "--as-of", "2026-04-25").exit_code == 0
        assert (a / "Patient.ndjson").read_text() == (b / "Patient.ndjson").read_text()

    def test_different_as_of_changes_ages(self, tmp_path):
        a, b = tmp_path / "a", tmp_path / "b"
        _gen(a, "--as-of", "2026-04-25")
        _gen(b, "--as-of", "2010-04-25")
        assert (a / "Patient.ndjson").read_text() != (b / "Patient.ndjson").read_text()

    def test_as_of_recorded_in_metadata(self, tmp_path):
        _gen(tmp_path, "--as-of", "2026-04-25")
        meta = json.loads((tmp_path / "generation-metadata.json").read_text())
        assert meta["as_of"] == "2026-04-25"

    def test_invalid_as_of_rejected(self, tmp_path):
        result = _gen(tmp_path, "--as-of", "not-a-date")
        assert result.exit_code == 1
        assert "invalid --as-of" in result.output

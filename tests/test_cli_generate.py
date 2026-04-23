"""End-to-end tests for `atlas generate`."""

from __future__ import annotations

import json

from fhir.resources.R4B.bundle import Bundle
from typer.testing import CliRunner

from parker_atlas.cli import app

runner = CliRunner()


def test_generate_writes_valid_bundles(tmp_path):
    result = runner.invoke(
        app,
        ["generate", "--patients", "5", "--seed", "42", "--out", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output

    files = sorted(tmp_path.glob("*.json"))
    assert len(files) == 5

    for f in files:
        assert f.name.startswith("GPX-SYN-")
        data = json.loads(f.read_text())
        Bundle.model_validate(data)
        assert data["type"] == "transaction"
        patient = data["entry"][0]["resource"]
        assert patient["resourceType"] == "Patient"


def test_generate_is_reproducible_with_seed(tmp_path):
    out_a = tmp_path / "a"
    out_b = tmp_path / "b"
    for path in (out_a, out_b):
        res = runner.invoke(
            app,
            ["generate", "--patients", "3", "--seed", "7", "--out", str(path)],
        )
        assert res.exit_code == 0, res.output

    files_a = sorted(p.name for p in out_a.glob("*.json"))
    files_b = sorted(p.name for p in out_b.glob("*.json"))
    assert files_a == files_b

    for name in files_a:
        assert (out_a / name).read_text() == (out_b / name).read_text()


def test_generate_rejects_unsupported_format(tmp_path):
    result = runner.invoke(
        app,
        ["generate", "--patients", "1", "--format", "ndjson", "--out", str(tmp_path)],
    )
    assert result.exit_code == 2
    assert "not yet supported" in result.output


def test_generate_rejects_module_flag(tmp_path):
    result = runner.invoke(
        app,
        ["generate", "--patients", "1", "--module", "type-2-diabetes", "--out", str(tmp_path)],
    )
    assert result.exit_code == 2


def test_generate_rejects_zero_patients(tmp_path):
    result = runner.invoke(
        app,
        ["generate", "--patients", "0", "--out", str(tmp_path)],
    )
    assert result.exit_code == 1


def test_status_command_works():
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "implemented" in result.output


def test_version_command_works():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "parker-atlas" in result.output

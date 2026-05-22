"""Tests for GTM-oriented CLI presets."""

from __future__ import annotations

from typer.testing import CliRunner

from parker_atlas.cli import GTM_HARDENED_MODULES, LAUNCH_DEMO_MODULES, app

runner = CliRunner()


def test_launch_demo_generates_valid_rich_cohort(tmp_path) -> None:
    out = tmp_path / "launch-demo"
    result = runner.invoke(
        app,
        [
            "launch-demo",
            "--patients", "8",
            "--seed", "42",
            "--out", str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    assert (out / "generation-metadata.json").exists()
    bundle_files = [
        p
        for p in out.glob("GPX-SYN-*.json")
        if p.name != "generation-metadata.json"
    ]
    assert len(bundle_files) == 8

    validated = runner.invoke(app, ["validate", str(out)])
    assert validated.exit_code == 0, validated.output


def test_validate_gtm_runs_hardened_expectation_set(tmp_path) -> None:
    out = tmp_path / "gtm"
    generated = runner.invoke(
        app,
        [
            "generate",
            "--patients", "40",
            "--seed", "7",
            "--module", ",".join(GTM_HARDENED_MODULES),
            "--out", str(out),
        ],
    )
    assert generated.exit_code == 0, generated.output

    result = runner.invoke(app, ["validate", str(out), "--gtm", "--min-samples", "1000"])
    assert result.exit_code == 0, result.output
    assert "GTM fidelity expectations" in result.output
    assert "Structural validation" in result.output


def test_launch_demo_modules_are_bundled() -> None:
    listed = runner.invoke(app, ["modules"])
    assert listed.exit_code == 0, listed.output
    for module_name in LAUNCH_DEMO_MODULES:
        assert module_name in listed.output

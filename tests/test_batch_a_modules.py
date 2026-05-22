"""Guardrails for the Batch A module expansion."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from parker_atlas.cli import app
from parker_atlas.modules import list_bundled_modules, load_module

runner = CliRunner()

BATCH_A_COMPLETION_MODULES = [
    "allergic_rhinitis",
    "atopic_dermatitis",
    "cataract",
    "epilepsy",
    "gout",
    "influenza",
    "peripheral_artery_disease",
    "venous_thromboembolism",
]


def _catalog_modules() -> set[str]:
    catalog = Path("docs/module-catalog.md").read_text(encoding="utf-8")
    modules: set[str] = set()
    in_library_table = False
    for line in catalog.splitlines():
        if line == "## Current Library":
            in_library_table = True
            continue
        if in_library_table and line == "## Count Summary":
            break
        if not in_library_table or not line.startswith("| "):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if not cells or cells[0] in {"Module", "---"}:
            continue
        modules.add(cells[0])
    return modules


def test_module_catalog_matches_bundled_library() -> None:
    assert _catalog_modules() == set(list_bundled_modules())


@pytest.mark.parametrize("module_name", BATCH_A_COMPLETION_MODULES)
def test_batch_a_completion_modules_load_with_citations(module_name: str) -> None:
    module = load_module(module_name)
    assert module.cites, f"{module_name} should carry at least one citation"
    assert module.conditions, f"{module_name} should declare at least one condition"
    assert any(condition.emits for condition in module.conditions)


@pytest.mark.parametrize("module_name", BATCH_A_COMPLETION_MODULES)
def test_batch_a_completion_modules_generate_valid_fhir(tmp_path, module_name: str) -> None:
    out = tmp_path / module_name
    generated = runner.invoke(
        app,
        [
            "generate",
            "--patients", "25",
            "--seed", "42",
            "--module", module_name,
            "--out", str(out),
        ],
    )
    assert generated.exit_code == 0, generated.output

    validated = runner.invoke(app, ["validate", str(out)])
    assert validated.exit_code == 0, validated.output

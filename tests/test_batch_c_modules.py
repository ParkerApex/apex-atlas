"""Guardrails for the Batch C module expansion to 100."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from parker_atlas.cli import app
from parker_atlas.modules import list_bundled_modules, load_module

runner = CliRunner()

BATCH_C_MODULES = [
    "acne",
    "acute_bronchitis",
    "adhd",
    "autism_spectrum_disorder",
    "cellulitis",
    "chronic_pain",
    "conjunctivitis",
    "constipation",
    "dental_caries",
    "diverticulitis",
    "endometriosis",
    "erectile_dysfunction",
    "fall_risk",
    "frailty",
    "hearing_loss",
    "insomnia",
    "menopause",
    "pancreatitis",
    "pcos",
    "postpartum_depression",
    "pressure_injury",
    "sepsis_survivorship",
    "sexual_health_sti",
    "thyroid_nodule",
    "uterine_fibroids",
]


def test_bundled_library_module_count() -> None:
    # 100-module launch library + glaucoma (the first `atlas author`-drafted,
    # Tier 3 post-launch addition).
    assert len(list_bundled_modules()) == 101


@pytest.mark.parametrize("module_name", BATCH_C_MODULES)
def test_batch_c_modules_load_with_citations(module_name: str) -> None:
    module = load_module(module_name)
    assert module.cites, f"{module_name} should carry at least one citation"
    assert module.conditions, f"{module_name} should declare at least one condition"
    assert any(condition.emits for condition in module.conditions)


@pytest.mark.parametrize("module_name", BATCH_C_MODULES)
def test_batch_c_modules_generate_valid_fhir(tmp_path, module_name: str) -> None:
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

"""Guardrails for the first Batch B module slice."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from parker_atlas.cli import app
from parker_atlas.modules import load_module

runner = CliRunner()

BATCH_B_START_MODULES = [
    "benign_prostatic_hyperplasia",
    "cardiomyopathy",
    "chronic_liver_disease",
    "covid19",
    "fibromyalgia",
    "gallbladder_disease",
    "hepatitis_c",
    "hyperthyroidism",
    "iron_deficiency_anemia",
    "lupus",
    "melanoma",
    "metabolic_syndrome",
    "nephrolithiasis",
    "osteoporosis",
    "osteoporosis_fracture",
    "otitis_media",
    "parkinsons_disease",
    "peripheral_neuropathy",
    "psoriasis",
    "pulmonary_embolism",
    "pulmonary_hypertension",
    "sinusitis",
    "traumatic_brain_injury",
    "urinary_incontinence",
    "valvular_heart_disease",
]


@pytest.mark.parametrize("module_name", BATCH_B_START_MODULES)
def test_batch_b_start_modules_load_with_citations(module_name: str) -> None:
    module = load_module(module_name)
    assert module.cites, f"{module_name} should carry at least one citation"
    assert module.conditions, f"{module_name} should declare at least one condition"
    assert any(condition.emits for condition in module.conditions)


@pytest.mark.parametrize("module_name", BATCH_B_START_MODULES)
def test_batch_b_start_modules_generate_valid_fhir(tmp_path, module_name: str) -> None:
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

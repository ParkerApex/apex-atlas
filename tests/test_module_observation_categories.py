"""Regression: every bundled module must generate without an unsupported
Observation category.

This guards a real bug: several modules emit `survey` (PHQ-9, GAD-7, AUDIT) and
`social-history` (smoking status) Observations. The FHIR Observation builder
once allowed only `vital-signs`/`laboratory`, so `atlas generate` crashed
mid-cohort for anxiety, alcohol_use_disorder, opioid_use_disorder,
bipolar_disorder, alzheimers_dementia, tobacco_use_disorder, and maternal_health
— and `atlas launch-demo` (which includes anxiety + maternal_health) with them.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from parker_atlas.cli import app
from parker_atlas.fhir.observation import SUPPORTED_CATEGORIES
from parker_atlas.modules.runtime import (
    ObservationEmit,
    list_bundled_modules,
    load_module,
)

runner = CliRunner()

# Modules that emit a non-(vital-signs|laboratory) Observation category — the
# exact set that used to crash generation. Kept explicit so the test is fast and
# the regression target is documented.
NON_STANDARD_CATEGORY_MODULES = [
    "anxiety",
    "alcohol_use_disorder",
    "opioid_use_disorder",
    "bipolar_disorder",
    "alzheimers_dementia",
    "tobacco_use_disorder",
    "maternal_health",
]


def test_all_emitted_observation_categories_are_supported():
    """No module may declare an Observation category the builder can't emit."""
    offenders: dict[str, set[str]] = {}
    for name in list_bundled_modules():
        module = load_module(name)
        for cond in module.conditions:
            for emit in cond.emits:
                if isinstance(emit, ObservationEmit) and emit.category not in SUPPORTED_CATEGORIES:
                    offenders.setdefault(name, set()).add(emit.category)
    assert not offenders, f"modules emit unsupported Observation categories: {offenders}"


@pytest.mark.parametrize("module_name", NON_STANDARD_CATEGORY_MODULES)
def test_module_generates_without_category_crash(tmp_path: Path, module_name: str):
    out = tmp_path / module_name
    result = runner.invoke(
        app,
        ["generate", "--module", module_name, "--patients", "800", "--seed", "3", "--out", str(out)],
    )
    assert result.exit_code == 0, result.output
    bundles = list(out.glob("GPX-SYN-*.json"))
    assert len(bundles) == 800, f"expected 800 bundles, got {len(bundles)}"

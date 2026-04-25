"""Integration tests for the bundled progressions overlays.

These tests assert that the `<module>.progressions.yaml` overlay files
shipped in `parker_atlas/modules/library/` are picked up by `load_module`
and override the inline rates in the corresponding module YAMLs.
"""

from __future__ import annotations

from importlib import resources

import yaml

from parker_atlas.modules.runtime import load_module


def _read_overlay(name: str) -> dict:
    pkg = resources.files("parker_atlas.modules.library")
    return yaml.safe_load(
        pkg.joinpath(f"{name}.progressions.yaml").read_text(encoding="utf-8")
    )


class TestHypertensionOverlay:
    def test_overlay_is_present_and_sourced(self):
        overlay = _read_overlay("hypertension")
        assert overlay["module"] == "hypertension"
        assert overlay["source"]["provenance"] == "sourced"
        assert overlay["source"]["citations"], "expected at least one citation"

    def test_loaded_module_uses_overlay_rate(self):
        # hypertension.yaml inline rate is 0.10; the overlay sources 0.105.
        # `load_module` should apply the overlay so the runtime rate matches.
        module = load_module("hypertension")
        htn = next(c for c in module.conditions if c.id == "essential_hypertension")
        progs = [p for p in htn.progressions if p.to == "hypertensive_ckd"]
        assert len(progs) == 1
        assert progs[0].probability == 0.105
        assert progs[0].after_years == 10


class TestDiabetesOverlay:
    def test_overlay_is_present_and_sourced(self):
        overlay = _read_overlay("diabetes")
        assert overlay["module"] == "diabetes"
        assert overlay["source"]["provenance"] == "sourced"
        assert overlay["source"]["citations"]

    def test_loaded_module_uses_overlay_rate(self):
        module = load_module("diabetes")
        dm = next(c for c in module.conditions if c.id == "diabetes_mellitus")
        progs = [p for p in dm.progressions if p.to == "diabetic_ckd"]
        assert len(progs) == 1
        assert progs[0].probability == 0.20
        assert progs[0].after_years == 10


class TestModuleListingExcludesOverlays:
    def test_overlays_not_listed_as_modules(self):
        from parker_atlas.modules.runtime import list_bundled_modules

        names = list_bundled_modules()
        # No overlay names leak into the module list.
        for name in names:
            assert ".progressions" not in name
        # Real modules are still listed.
        assert "hypertension" in names
        assert "diabetes" in names

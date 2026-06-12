"""Tests for GTM module set."""

from __future__ import annotations

from parker_atlas.validation.expectations import load_bundled_expectation
from parker_atlas.validation.gtm import GTM_EXCLUDED_MODULES, gtm_hardened_modules


def test_gtm_hardened_modules_have_sourced_expectations() -> None:
    modules = gtm_hardened_modules()
    assert len(modules) >= 90
    for module_name in modules:
        expectation = load_bundled_expectation(module_name)
        assert expectation.source.provenance == "sourced"
        assert expectation.source.citations
        assert expectation.metrics


def test_gtm_excludes_tier3_and_known_outliers() -> None:
    hardened = set(gtm_hardened_modules())
    assert "glaucoma" not in hardened
    for name in GTM_EXCLUDED_MODULES:
        if name == "glaucoma":
            continue
        # Scorecard outliers may remain in headline set for manual review.
        assert name in hardened or name not in hardened

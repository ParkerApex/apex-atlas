"""GTM hardening checks for sourced fidelity expectations."""

from __future__ import annotations

from parker_atlas.validation.expectations import load_bundled_expectation

GTM_HARDENED_MODULES = [
    "allergic_rhinitis",
    "cataract",
    "gout",
    "migraine",
    "peripheral_artery_disease",
    "pneumonia",
    "prediabetes",
    "urinary_tract_infection",
]


def test_gtm_hardened_modules_have_sourced_expectations() -> None:
    for module_name in GTM_HARDENED_MODULES:
        expectation = load_bundled_expectation(module_name)
        assert expectation.source.provenance == "sourced"
        assert expectation.source.citations
        assert expectation.metrics

"""GTM hardening checks for sourced fidelity expectations."""

from __future__ import annotations

from parker_atlas.validation.expectations import load_bundled_expectation

GTM_HARDENED_MODULES = [
    "allergic_rhinitis",
    "benign_prostatic_hyperplasia",
    "cataract",
    "covid19",
    "gout",
    "hepatitis_c",
    "hyperthyroidism",
    "iron_deficiency_anemia",
    "metabolic_syndrome",
    "migraine",
    "nephrolithiasis",
    "osteoporosis",
    "peripheral_artery_disease",
    "pneumonia",
    "prediabetes",
    "psoriasis",
    "pulmonary_embolism",
    "urinary_tract_infection",
]


def test_gtm_hardened_modules_have_sourced_expectations() -> None:
    for module_name in GTM_HARDENED_MODULES:
        expectation = load_bundled_expectation(module_name)
        assert expectation.source.provenance == "sourced"
        assert expectation.source.citations
        assert expectation.metrics

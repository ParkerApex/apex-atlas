"""Launch-hardened module set for `atlas validate --gtm`."""

from __future__ import annotations

from parker_atlas.validation.expectations import (
    list_bundled_expectations,
    load_bundled_expectation,
)

# Tier 3 modules excluded from headline GTM validation.
GTM_EXCLUDED_MODULES = frozenset(
    {
        "glaucoma",  # Tier 3 — pending licensed clinician sign-off
    }
)

# Headline launch modules always included even if expectations are added later.
GTM_HEADLINE_MODULES = frozenset(
    {
        "hypertension",
        "diabetes",
        "prediabetes",
        "heart_failure",
        "asthma",
        "copd",
        "depression",
        "wellness",
        "pediatric_wellness",
        "maternal_health",
        "stroke",
        "ckd",
        "obesity",
        "hypercholesterolemia",
        "ischemic_heart_disease",
    }
)


def gtm_hardened_modules() -> list[str]:
    """Modules run by `atlas validate --gtm` (structural + cohort fidelity)."""
    bundled: set[str] = set()
    for name in list_bundled_expectations():
        if name in GTM_EXCLUDED_MODULES:
            continue
        expectation = load_bundled_expectation(name)
        if expectation.source.provenance != "sourced":
            continue
        bundled.add(name)
    return sorted(
        m
        for m in (bundled | (GTM_HEADLINE_MODULES - GTM_EXCLUDED_MODULES))
        if load_bundled_expectation(m).source.provenance == "sourced"
    )

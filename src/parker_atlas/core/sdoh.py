"""
Social Determinants of Health (SDoH) profile sampling.

Samples a per-patient SDoH risk profile from BRFSS-grounded population
distributions. The profile has two roles:

1. **Causal modifiers** — float multipliers (0.0–1.0) that downstream
   code applies to encounter and medication emit probabilities, making
   SDoH a first-class variable in patient simulation rather than a
   metadata tag. A patient with high transport burden completes fewer
   outpatient encounters; a patient with cost barriers fills fewer
   prescriptions.

2. **FHIR Observation inputs** — each sampled domain is also emitted
   as a structured Gravity Project / SDOHCC Observation so that the
   patient's bundle carries machine-readable SDoH context.

Population sources:
- BRFSS 2022 — food insecurity (~17% of US adults), inadequate housing
  (~8%), transportation barriers (~12%), financial strain (~31%).
- CDC Social Vulnerability Index (SVI) — socioeconomic and housing
  dimensions used to calibrate overall burden rates.
- Karpman et al. (Urban Institute, 2022) — cost-related medication
  non-adherence ~19% of adults with prescriptions.

Rates are age-stratified but not sex-stratified at this cut (a future
ingestion pass via `atlas ingest prevalence` can add sex stratification
when cited data are available).

Notes on modeling choices:
- We do not apply a joint copula across SDoH domains — each domain is
  sampled independently. Real-world SDoH domains are correlated (e.g.,
  food insecurity and housing instability co-occur), but capturing that
  correlation requires a multivariate model beyond the scope of this first
  version. Independent sampling slightly understates clustering of burden.
- `encounter_completion_rate` and `medication_adherence_rate` are
  derived from the domain flags, not from separate surveys. The decay
  weights below are calibrated to approximate BRFSS-reported care
  avoidance rates by burden level.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class SDoHProfile:
    """Per-patient SDoH risk profile.

    Boolean flags mark which risk domains are active for this patient.
    Derived float modifiers are pre-computed so downstream code doesn't
    need to re-derive them on every encounter.

    Modifier semantics:
    - `encounter_completion_rate`: multiply against the probability that
      an outpatient (AMB) encounter actually occurs. A value of 0.7 means
      the patient misses ~30% of outpatient visits due to transport or
      cost barriers. Inpatient (IMP) and emergency (EMER) encounters are
      not reduced — those represent care-seeking despite barriers.
    - `medication_adherence_rate`: multiply against the probability that
      a MedicationRequest is emitted. A value of 0.75 means ~25% of
      indicated medications are not prescribed or not filled due to cost.
    """

    # Domain flags
    food_insecurity: bool = False
    housing_instability: bool = False
    transportation_barrier: bool = False
    financial_strain: bool = False
    inadequate_social_support: bool = False

    # Derived causal modifiers (computed at construction via __post_init__
    # workaround — frozen dataclass, so computed in the factory function)
    encounter_completion_rate: float = 1.0
    medication_adherence_rate: float = 1.0

    @property
    def any_risk(self) -> bool:
        return any(
            [
                self.food_insecurity,
                self.housing_instability,
                self.transportation_barrier,
                self.financial_strain,
                self.inadequate_social_support,
            ]
        )

    @property
    def active_domains(self) -> list[str]:
        domains = []
        if self.food_insecurity:
            domains.append("food_insecurity")
        if self.housing_instability:
            domains.append("housing_instability")
        if self.transportation_barrier:
            domains.append("transportation_barrier")
        if self.financial_strain:
            domains.append("financial_strain")
        if self.inadequate_social_support:
            domains.append("inadequate_social_support")
        return domains


def _compute_encounter_rate(
    transportation_barrier: bool,
    financial_strain: bool,
    housing_instability: bool,
) -> float:
    """Derive encounter completion rate from relevant SDoH flags.

    Anchored to BRFSS care avoidance estimates:
    - Transportation barrier alone → ~15% visit non-completion
    - Financial strain alone → ~20% visit non-completion
    - Both → ~30% non-completion (not purely additive)
    - Housing instability adds ~5% additional
    """
    rate = 1.0
    if transportation_barrier:
        rate *= 0.85
    if financial_strain:
        rate *= 0.80
    if housing_instability:
        rate *= 0.95
    return round(max(rate, 0.40), 3)


def _compute_medication_rate(
    financial_strain: bool,
    food_insecurity: bool,
) -> float:
    """Derive medication adherence rate from relevant SDoH flags.

    Karpman et al. (Urban Institute 2022): ~19% of adults with
    prescriptions report cost-related non-adherence. Among adults
    with financial strain the rate is ~28%.
    """
    rate = 1.0
    if financial_strain:
        rate *= 0.72
    if food_insecurity:
        rate *= 0.90
    return round(max(rate, 0.40), 3)


# Age-stratified SDoH prevalence rates from BRFSS 2022 and Urban Institute.
# Each entry is (food_insecurity, housing_instability, transport_barrier,
# financial_strain, inadequate_social_support).
# Brackets: 0-17, 18-34, 35-49, 50-64, 65-99.
_RATES_BY_AGE_BRACKET: list[tuple[tuple[int, int], tuple[float, float, float, float, float]]] = [
    ((0, 17),   (0.18, 0.10, 0.10, 0.28, 0.15)),  # children tracked via HH
    ((18, 34),  (0.22, 0.14, 0.14, 0.38, 0.18)),  # highest financial strain
    ((35, 49),  (0.18, 0.10, 0.13, 0.33, 0.15)),
    ((50, 64),  (0.15, 0.07, 0.12, 0.28, 0.16)),
    ((65, 99),  (0.09, 0.04, 0.11, 0.18, 0.22)),  # higher social isolation
]


def _rates_for_age(age: int) -> tuple[float, float, float, float, float]:
    for (lo, hi), rates in _RATES_BY_AGE_BRACKET:
        if lo <= age <= hi:
            return rates
    return _RATES_BY_AGE_BRACKET[-1][1]  # fallback: 65+


def sample_sdoh(rng: random.Random, age_years: int) -> SDoHProfile:
    """Sample a SDoH risk profile for one patient.

    Each domain is an independent Bernoulli trial against its age-
    stratified prevalence rate. Returns a `SDoHProfile` with derived
    causal modifiers pre-computed.

    Args:
        rng: seeded Random instance from the generate loop.
        age_years: patient's age in years at simulation date.
    """
    fi_rate, hi_rate, tb_rate, fs_rate, ss_rate = _rates_for_age(age_years)

    food_insecurity = rng.random() < fi_rate
    housing_instability = rng.random() < hi_rate
    transportation_barrier = rng.random() < tb_rate
    financial_strain = rng.random() < fs_rate
    inadequate_social_support = rng.random() < ss_rate

    encounter_rate = _compute_encounter_rate(
        transportation_barrier=transportation_barrier,
        financial_strain=financial_strain,
        housing_instability=housing_instability,
    )
    medication_rate = _compute_medication_rate(
        financial_strain=financial_strain,
        food_insecurity=food_insecurity,
    )

    return SDoHProfile(
        food_insecurity=food_insecurity,
        housing_instability=housing_instability,
        transportation_barrier=transportation_barrier,
        financial_strain=financial_strain,
        inadequate_social_support=inadequate_social_support,
        encounter_completion_rate=encounter_rate,
        medication_adherence_rate=medication_rate,
    )

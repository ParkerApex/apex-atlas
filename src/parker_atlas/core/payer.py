"""
Payer-mix sampling for synthetic patient coverage assignment.

Two-stage draw:

1. Sample `payer_type` (medicare | medicare-advantage | medicaid | commercial
   | uninsured) from the age-stratified `payer_mix` table. Brackets must be
   non-overlapping and span all ages a generator might produce.
2. If the type maps to one or more concrete payers in the `payers` table,
   draw a specific payer by intra-type weight. The "uninsured" type yields
   `None`, signaling that no Coverage / payer Organization should be built.

`Payer.payer_type` distinguishes regulatory category (drives downstream
profile selection in the Coverage builder — Medicare → CMS reference,
Medicaid → state plan reference, etc.).
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from parker_atlas.references import (
    PayerMixRow,
    PayerRow,
    load_payer_mix,
    load_payers,
)


@dataclass(frozen=True, slots=True)
class Payer:
    payer_id: str
    name: str
    payer_type: str


UNINSURED_TYPE = "uninsured"


def _bracket_for_age(age_years: int, rows: tuple[PayerMixRow, ...]) -> tuple[int, int]:
    for r in rows:
        if r.age_low <= age_years <= r.age_high:
            return (r.age_low, r.age_high)
    raise ValueError(f"no payer_mix bracket covers age {age_years}")


def sample_payer(rng: random.Random, *, age_years: int) -> Payer | None:
    """Draw a payer for a patient by age. Returns None when uninsured."""
    mix = load_payer_mix()
    bracket = _bracket_for_age(age_years, mix)
    bracket_rows = [
        r for r in mix if (r.age_low, r.age_high) == bracket
    ]
    payer_type = rng.choices(
        [r.payer_type for r in bracket_rows],
        weights=[r.weight for r in bracket_rows],
        k=1,
    )[0]

    if payer_type == UNINSURED_TYPE:
        return None

    payers = [p for p in load_payers() if p.payer_type == payer_type]
    if not payers:
        raise ValueError(
            f"payer_type {payer_type!r} declared in payer_mix has no concrete "
            f"payers in payers.csv"
        )
    pick: PayerRow = rng.choices(
        payers, weights=[p.weight_within_type for p in payers], k=1
    )[0]
    return Payer(payer_id=pick.payer_id, name=pick.name, payer_type=pick.payer_type)

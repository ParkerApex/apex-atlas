"""Payer-mix sampling tests."""

from __future__ import annotations

import random
from collections import Counter

import pytest

from parker_atlas.core.payer import UNINSURED_TYPE, sample_payer
from parker_atlas.references import load_payer_mix, load_payers


def test_payer_mix_table_brackets_are_non_overlapping():
    rows = load_payer_mix()
    brackets = sorted({(r.age_low, r.age_high) for r in rows})
    # Brackets must be non-overlapping and contiguous.
    for (lo1, hi1), (lo2, hi2) in zip(brackets, brackets[1:], strict=False):
        assert hi1 + 1 == lo2, f"gap between {hi1} and {lo2}"


def test_payer_mix_weights_sum_to_one_per_bracket():
    rows = load_payer_mix()
    by_bracket: dict[tuple[int, int], list[float]] = {}
    for r in rows:
        by_bracket.setdefault((r.age_low, r.age_high), []).append(r.weight)
    for bracket, weights in by_bracket.items():
        assert abs(sum(weights) - 1.0) < 1e-6, f"bracket {bracket} weights sum to {sum(weights)}"


def test_every_non_uninsured_payer_type_resolves_to_at_least_one_payer():
    declared_types = {r.payer_type for r in load_payer_mix() if r.payer_type != UNINSURED_TYPE}
    available_types = {p.payer_type for p in load_payers()}
    assert declared_types.issubset(available_types), (
        f"payer_mix references types missing from payers: "
        f"{declared_types - available_types}"
    )


@pytest.mark.parametrize(
    ("age", "expected_dominant_type"),
    [
        (5, "commercial"),
        (30, "commercial"),
        (75, "medicare"),
    ],
)
def test_sample_payer_matches_table_dominant_type(age: int, expected_dominant_type: str) -> None:
    rng = random.Random(42)
    types: Counter[str] = Counter()
    for _ in range(2000):
        p = sample_payer(rng, age_years=age)
        types[p.payer_type if p else "uninsured"] += 1
    assert types.most_common(1)[0][0] == expected_dominant_type


def test_sample_payer_uninsured_returns_none():
    # Force a deterministic seed where uninsured is plausible (18-64 bracket
    # gives uninsured ~13%); we don't assert frequency, only that None is a
    # possible return value when the type lands.
    rng = random.Random(0)
    saw_none = False
    saw_payer = False
    for _ in range(500):
        p = sample_payer(rng, age_years=30)
        if p is None:
            saw_none = True
        else:
            saw_payer = True
            assert p.payer_type != UNINSURED_TYPE
    assert saw_none and saw_payer

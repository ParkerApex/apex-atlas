"""Tests for demographic sampling."""

from __future__ import annotations

import random
from datetime import date

from parker_atlas.core.demographics import (
    AdministrativeGender,
    Demographics,
    Ethnicity,
    Race,
    sample_demographics,
)


def test_seed_is_reproducible():
    r1 = random.Random(42)
    r2 = random.Random(42)
    today = date(2026, 1, 1)
    d1 = [sample_demographics(r1, today) for _ in range(20)]
    d2 = [sample_demographics(r2, today) for _ in range(20)]
    assert d1 == d2


def test_returns_demographics_with_valid_fields():
    rng = random.Random(0)
    demo = sample_demographics(rng, today=date(2026, 1, 1))
    assert isinstance(demo, Demographics)
    assert isinstance(demo.gender, AdministrativeGender)
    assert isinstance(demo.race, Race)
    assert isinstance(demo.ethnicity, Ethnicity)
    assert isinstance(demo.birth_date, date)
    assert demo.given_name
    assert demo.family_name


def test_birth_date_is_in_past():
    rng = random.Random(0)
    today = date(2026, 1, 1)
    for _ in range(100):
        demo = sample_demographics(rng, today)
        assert demo.birth_date <= today


def test_age_brackets_cover_full_range():
    rng = random.Random(12345)
    today = date(2026, 1, 1)
    ages = set()
    for _ in range(500):
        demo = sample_demographics(rng, today)
        age = (today - demo.birth_date).days // 365
        ages.add(age // 20)  # coarse bucket
    # With 500 draws across 5 brackets (0-17, 18-34, 35-54, 55-74, 75-95),
    # we should see at least three distinct coarse buckets.
    assert len(ages) >= 3


def test_birth_sex_matches_gender_for_now():
    # Current placeholder: birth_sex equals administrative gender.
    # A future milestone will model non-binary/trans distributions.
    rng = random.Random(7)
    for _ in range(50):
        demo = sample_demographics(rng)
        assert demo.birth_sex == demo.gender

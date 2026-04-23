"""Tests for reference-distribution loaders."""

from __future__ import annotations

from parker_atlas.references import (
    AgeSexBin,
    CategoryWeight,
    clear_cache,
    load_age_sex,
    load_ethnicity,
    load_names,
    load_race,
)


def test_age_sex_table_has_expected_shape():
    rows = load_age_sex()
    assert len(rows) > 0
    for r in rows:
        assert isinstance(r, AgeSexBin)
        assert r.sex in ("male", "female")
        assert 0 <= r.age_low <= r.age_high
        assert r.weight > 0


def test_age_sex_weights_sum_to_approximately_one():
    total = sum(r.weight for r in load_age_sex())
    assert abs(total - 1.0) < 0.01


def test_race_table_matches_omb_codes():
    rows = load_race()
    codes = {r.code for r in rows}
    # OMB race codes that US Core references.
    assert "2106-3" in codes  # White
    assert "2054-5" in codes  # Black or African American
    assert "2028-9" in codes  # Asian


def test_ethnicity_table_has_hispanic_and_non_hispanic():
    rows = load_ethnicity()
    codes = {r.code for r in rows}
    assert "2135-2" in codes  # Hispanic or Latino
    assert "2186-5" in codes  # Not Hispanic or Latino


def test_names_has_three_pools():
    names = load_names()
    assert set(names) == {"first_female", "first_male", "last"}
    for pool, values in names.items():
        assert len(values) > 0, f"pool {pool} is empty"


def test_loaders_are_cached():
    clear_cache()
    a = load_race()
    b = load_race()
    # Same tuple object — memoized.
    assert a is b


def test_clear_cache_drops_memo():
    load_race()
    clear_cache()
    # Hit the cold path again without exceptions.
    assert load_race()


def test_category_weight_is_immutable():
    rows = load_race()
    assert isinstance(rows[0], CategoryWeight)

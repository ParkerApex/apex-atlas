"""
Demographic sampling for synthetic patient generation.

Distributions live in `parker_atlas/references/tables/*.csv` and are
loaded through `parker_atlas.references`. They are currently curated
placeholders; real US Census ACS ingestion is tracked under Milestone 1
follow-up work in `docs/roadmap.md`.

Sampling structure:
- `age_sex.csv` provides a joint age-bracket × sex distribution. A
  single draw yields (age_bracket, sex), preserving the slight sex
  imbalance that varies by bracket (e.g. women live longer).
- `race.csv` and `ethnicity.csv` are marginal OMB-category distributions,
  drawn independently of age and sex. Joint modeling with age/sex lands
  when ACS data replaces the placeholders.
- `names.csv` provides three pools keyed by sex + surname.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum

from parker_atlas.references import (
    AgeSexBin,
    CategoryWeight,
    load_age_sex,
    load_ethnicity,
    load_names,
    load_race,
)


class AdministrativeGender(str, Enum):
    MALE = "male"
    FEMALE = "female"


class Race(str, Enum):
    """OMB race categories used by the US Core race extension."""

    WHITE = "2106-3"
    BLACK = "2054-5"
    AMERICAN_INDIAN = "1002-5"
    ASIAN = "2028-9"
    PACIFIC_ISLANDER = "2076-8"
    OTHER = "2131-1"


class Ethnicity(str, Enum):
    """OMB ethnicity categories used by the US Core ethnicity extension."""

    HISPANIC = "2135-2"
    NON_HISPANIC = "2186-5"


def race_display(race: Race) -> str:
    """Return the human-readable label for an OMB race code."""
    for row in load_race():
        if row.code == race.value:
            return row.display
    raise KeyError(race)


def ethnicity_display(ethnicity: Ethnicity) -> str:
    """Return the human-readable label for an OMB ethnicity code."""
    for row in load_ethnicity():
        if row.code == ethnicity.value:
            return row.display
    raise KeyError(ethnicity)


@dataclass(frozen=True, slots=True)
class Demographics:
    given_name: str
    family_name: str
    gender: AdministrativeGender
    birth_date: date
    race: Race
    ethnicity: Ethnicity
    birth_sex: AdministrativeGender


def _weighted_choice_bin(rng: random.Random, bins: tuple[AgeSexBin, ...]) -> AgeSexBin:
    weights = [b.weight for b in bins]
    return rng.choices(list(bins), weights=weights, k=1)[0]


def _weighted_choice_category(
    rng: random.Random, rows: tuple[CategoryWeight, ...]
) -> CategoryWeight:
    weights = [r.weight for r in rows]
    return rng.choices(list(rows), weights=weights, k=1)[0]


def sample_demographics(rng: random.Random, today: date | None = None) -> Demographics:
    """Draw a single synthetic demographic record from the reference tables."""
    today = today or date.today()

    age_sex = _weighted_choice_bin(rng, load_age_sex())
    gender = AdministrativeGender(age_sex.sex)
    age_years = rng.randint(age_sex.age_low, age_sex.age_high)
    days_back = age_years * 365 + rng.randint(0, 364)
    birth_date = today - timedelta(days=days_back)

    race = Race(_weighted_choice_category(rng, load_race()).code)
    ethnicity = Ethnicity(_weighted_choice_category(rng, load_ethnicity()).code)

    names = load_names()
    first_pool = "first_female" if gender is AdministrativeGender.FEMALE else "first_male"
    given = rng.choice(names[first_pool])
    family = rng.choice(names["last"])

    return Demographics(
        given_name=given,
        family_name=family,
        gender=gender,
        birth_date=birth_date,
        race=race,
        ethnicity=ethnicity,
        birth_sex=gender,
    )

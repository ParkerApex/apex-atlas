"""
Demographic sampling for synthetic patient generation.

This module provides placeholder distributions used by the Milestone 1
vertical slice. The distributions below are rough approximations of US
population marginals; they will be replaced with calibrated samples from
US Census ACS microdata in a follow-up milestone.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum


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


RACE_DISPLAY: dict[Race, str] = {
    Race.WHITE: "White",
    Race.BLACK: "Black or African American",
    Race.AMERICAN_INDIAN: "American Indian or Alaska Native",
    Race.ASIAN: "Asian",
    Race.PACIFIC_ISLANDER: "Native Hawaiian or Other Pacific Islander",
    Race.OTHER: "Other Race",
}


class Ethnicity(str, Enum):
    """OMB ethnicity categories used by the US Core ethnicity extension."""

    HISPANIC = "2135-2"
    NON_HISPANIC = "2186-5"


ETHNICITY_DISPLAY: dict[Ethnicity, str] = {
    Ethnicity.HISPANIC: "Hispanic or Latino",
    Ethnicity.NON_HISPANIC: "Not Hispanic or Latino",
}


# Placeholder distributions. Rough US population marginals — replace with
# ACS-backed samplers before any statistical-fidelity claims.
_GENDER_DIST: list[tuple[AdministrativeGender, float]] = [
    (AdministrativeGender.FEMALE, 0.505),
    (AdministrativeGender.MALE, 0.495),
]

_RACE_DIST: list[tuple[Race, float]] = [
    (Race.WHITE, 0.59),
    (Race.BLACK, 0.13),
    (Race.ASIAN, 0.06),
    (Race.AMERICAN_INDIAN, 0.01),
    (Race.PACIFIC_ISLANDER, 0.003),
    (Race.OTHER, 0.207),
]

_ETHNICITY_DIST: list[tuple[Ethnicity, float]] = [
    (Ethnicity.HISPANIC, 0.19),
    (Ethnicity.NON_HISPANIC, 0.81),
]

_AGE_BRACKETS: list[tuple[tuple[int, int], float]] = [
    ((0, 17), 0.22),
    ((18, 34), 0.23),
    ((35, 54), 0.26),
    ((55, 74), 0.22),
    ((75, 95), 0.07),
]

_FIRST_NAMES_F = [
    "Mary", "Patricia", "Jennifer", "Linda", "Elizabeth", "Barbara",
    "Susan", "Jessica", "Sarah", "Karen", "Nancy", "Lisa", "Margaret",
    "Betty", "Sandra", "Ashley", "Dorothy", "Kimberly", "Emily", "Donna",
]
_FIRST_NAMES_M = [
    "James", "Robert", "John", "Michael", "David", "William", "Richard",
    "Joseph", "Thomas", "Christopher", "Charles", "Daniel", "Matthew",
    "Anthony", "Mark", "Donald", "Steven", "Paul", "Andrew", "Joshua",
]
_LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez",
    "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
]


@dataclass(frozen=True, slots=True)
class Demographics:
    given_name: str
    family_name: str
    gender: AdministrativeGender
    birth_date: date
    race: Race
    ethnicity: Ethnicity
    birth_sex: AdministrativeGender


def _weighted_choice(rng: random.Random, options: list[tuple]) -> object:
    items, weights = zip(*options, strict=True)
    return rng.choices(list(items), weights=list(weights), k=1)[0]


def sample_demographics(rng: random.Random, today: date | None = None) -> Demographics:
    """Draw a single synthetic demographic record from the placeholder distributions."""
    today = today or date.today()

    gender = _weighted_choice(rng, _GENDER_DIST)
    age_lo, age_hi = _weighted_choice(rng, _AGE_BRACKETS)
    age_years = rng.randint(age_lo, age_hi)
    days_back = age_years * 365 + rng.randint(0, 364)
    birth_date = today - timedelta(days=days_back)

    race = _weighted_choice(rng, _RACE_DIST)
    ethnicity = _weighted_choice(rng, _ETHNICITY_DIST)

    pool = _FIRST_NAMES_F if gender is AdministrativeGender.FEMALE else _FIRST_NAMES_M
    given = rng.choice(pool)
    family = rng.choice(_LAST_NAMES)

    return Demographics(
        given_name=given,
        family_name=family,
        gender=gender,
        birth_date=birth_date,
        race=race,
        ethnicity=ethnicity,
        birth_sex=gender,
    )

"""
Reference distribution loader.

Exposes cached, structured access to the CSV tables in `tables/`. Each
loader is memoized; call `clear_cache()` (rarely needed) to force a
reread, for example in tests that monkeypatch the tables.

Distribution provenance is described in `tables/README.md`. The current
distributions are curated placeholders and are not yet ACS-derived.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources


@dataclass(frozen=True, slots=True)
class AgeSexBin:
    age_low: int
    age_high: int
    sex: str
    weight: float


@dataclass(frozen=True, slots=True)
class CategoryWeight:
    code: str
    display: str
    weight: float


@dataclass(frozen=True, slots=True)
class PayerRow:
    payer_id: str
    name: str
    payer_type: str
    weight_within_type: float


@dataclass(frozen=True, slots=True)
class PayerMixRow:
    age_low: int
    age_high: int
    payer_type: str
    weight: float


@dataclass(frozen=True, slots=True)
class PractitionerRow:
    npi: str
    family: str
    given: str
    prefix: str
    taxonomy_code: str
    taxonomy_display: str
    encounter_class: str


@dataclass(frozen=True, slots=True)
class LocationRow:
    facility_npi: str
    facility_name: str
    facility_role: str
    location_name: str
    location_type_code: str
    location_type_display: str
    line: str
    city: str
    state: str
    postal_code: str


_PACKAGE = "parker_atlas.references.tables"


def _read_csv(filename: str) -> list[dict[str, str]]:
    with resources.files(_PACKAGE).joinpath(filename).open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


@lru_cache(maxsize=1)
def load_age_sex() -> tuple[AgeSexBin, ...]:
    return tuple(
        AgeSexBin(
            age_low=int(r["age_low"]),
            age_high=int(r["age_high"]),
            sex=r["sex"],
            weight=float(r["weight"]),
        )
        for r in _read_csv("age_sex.csv")
    )


@lru_cache(maxsize=1)
def load_race() -> tuple[CategoryWeight, ...]:
    return tuple(
        CategoryWeight(code=r["code"], display=r["display"], weight=float(r["weight"]))
        for r in _read_csv("race.csv")
    )


@lru_cache(maxsize=1)
def load_ethnicity() -> tuple[CategoryWeight, ...]:
    return tuple(
        CategoryWeight(code=r["code"], display=r["display"], weight=float(r["weight"]))
        for r in _read_csv("ethnicity.csv")
    )


@lru_cache(maxsize=1)
def load_names() -> dict[str, tuple[str, ...]]:
    pools: dict[str, list[str]] = {}
    for row in _read_csv("names.csv"):
        pools.setdefault(row["pool"], []).append(row["name"])
    return {pool: tuple(names) for pool, names in pools.items()}


@lru_cache(maxsize=1)
def load_payers() -> tuple[PayerRow, ...]:
    return tuple(
        PayerRow(
            payer_id=r["payer_id"],
            name=r["name"],
            payer_type=r["payer_type"],
            weight_within_type=float(r["weight_within_type"]),
        )
        for r in _read_csv("payers.csv")
    )


@lru_cache(maxsize=1)
def load_payer_mix() -> tuple[PayerMixRow, ...]:
    return tuple(
        PayerMixRow(
            age_low=int(r["age_low"]),
            age_high=int(r["age_high"]),
            payer_type=r["payer_type"],
            weight=float(r["weight"]),
        )
        for r in _read_csv("payer_mix.csv")
    )


@lru_cache(maxsize=1)
def load_practitioners() -> tuple[PractitionerRow, ...]:
    return tuple(
        PractitionerRow(
            npi=r["npi"],
            family=r["family"],
            given=r["given"],
            prefix=r["prefix"],
            taxonomy_code=r["taxonomy_code"],
            taxonomy_display=r["taxonomy_display"],
            encounter_class=r["encounter_class"],
        )
        for r in _read_csv("practitioners.csv")
    )


@lru_cache(maxsize=1)
def load_locations() -> tuple[LocationRow, ...]:
    return tuple(
        LocationRow(
            facility_npi=r["facility_npi"],
            facility_name=r["facility_name"],
            facility_role=r["facility_role"],
            location_name=r["location_name"],
            location_type_code=r["location_type_code"],
            location_type_display=r["location_type_display"],
            line=r["line"],
            city=r["city"],
            state=r["state"],
            postal_code=r["postal_code"],
        )
        for r in _read_csv("locations.csv")
    )


def clear_cache() -> None:
    """Clear all memoized loaders. Primarily for tests."""
    load_age_sex.cache_clear()
    load_race.cache_clear()
    load_ethnicity.cache_clear()
    load_names.cache_clear()
    load_payers.cache_clear()
    load_payer_mix.cache_clear()
    load_practitioners.cache_clear()
    load_locations.cache_clear()

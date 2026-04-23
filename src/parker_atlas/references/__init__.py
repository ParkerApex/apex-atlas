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


def clear_cache() -> None:
    """Clear all memoized loaders. Primarily for tests."""
    load_age_sex.cache_clear()
    load_race.cache_clear()
    load_ethnicity.cache_clear()
    load_names.cache_clear()

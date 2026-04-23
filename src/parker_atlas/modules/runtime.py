"""
Clinical module runtime — probability-module flavor.

Parker Atlas modules are authored in YAML. The minimal flavor supported
today is a **probability module**: each condition carries an age-bracketed
(optionally sex-stratified) prevalence. For each patient, each condition
is a Bernoulli trial against its bracket-specific rate.

This is deliberately simpler than the state-machine DSL described in
`docs/architecture.md`. State machines (onset timing, progression,
resolution, medication cascades) land in a later milestone; the
probability flavor is the floor, not the ceiling.

Module YAML shape:
    module: <name>
    version: <semver>
    description: <str>
    cites:
      - source: <str>
        url: <str>
        summary: <str>
    conditions:
      - id: <short_identifier>
        code:
          system: <terminology-system-url>
          code: <terminology-code>
          display: <human-readable>
        prevalence:
          "0-17": 0.04
          "18-34": 0.22
          ...
          # Optionally sex-stratified:
          # female:
          #   "0-17": 0.03
          #   ...
          # male:
          #   "0-17": 0.05
          #   ...
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from importlib import resources
from typing import Any

import yaml


@dataclass(frozen=True, slots=True)
class Coding:
    system: str
    code: str
    display: str


@dataclass(frozen=True, slots=True)
class Citation:
    source: str
    url: str
    summary: str = ""


@dataclass(frozen=True, slots=True)
class ConditionSpec:
    """One condition a module can assign to a patient."""

    id: str
    code: Coding
    # Bracket key is (age_low, age_high) inclusive. Optional sex stratification
    # keys the outer dict by "female" | "male"; None means the inner dict is
    # used for all sexes.
    prevalence_by_bracket: dict[tuple[int, int], float]
    prevalence_by_sex: dict[str, dict[tuple[int, int], float]] | None = None


@dataclass(frozen=True, slots=True)
class Module:
    name: str
    version: str
    description: str
    cites: tuple[Citation, ...]
    conditions: tuple[ConditionSpec, ...]


@dataclass(frozen=True, slots=True)
class Diagnosis:
    """Output of run_module: a condition the module says this patient has."""

    condition: ConditionSpec


class ModuleError(ValueError):
    """Raised when a module file cannot be parsed or validated."""


# -- Parsing -----------------------------------------------------------------


def _parse_bracket(s: str) -> tuple[int, int]:
    try:
        lo_str, hi_str = s.split("-")
        return int(lo_str), int(hi_str)
    except ValueError as exc:
        raise ModuleError(f"invalid bracket {s!r}; expected 'LOW-HIGH'") from exc


def _parse_prevalence(
    raw: dict[str, Any],
) -> tuple[
    dict[tuple[int, int], float],
    dict[str, dict[tuple[int, int], float]] | None,
]:
    sex_keys = {"female", "male"}
    if set(raw.keys()) & sex_keys:
        # Sex-stratified form.
        by_sex: dict[str, dict[tuple[int, int], float]] = {}
        for sex, brackets in raw.items():
            if sex not in sex_keys:
                raise ModuleError(
                    f"sex-stratified prevalence keys must be in {sorted(sex_keys)}, "
                    f"got {sex!r}"
                )
            by_sex[sex] = {_parse_bracket(k): float(v) for k, v in brackets.items()}
        return {}, by_sex
    flat = {_parse_bracket(k): float(v) for k, v in raw.items()}
    return flat, None


def _parse_condition(raw: dict[str, Any]) -> ConditionSpec:
    try:
        code = Coding(**raw["code"])
    except TypeError as exc:
        raise ModuleError(f"condition {raw.get('id')!r} has malformed code: {exc}") from exc

    prevalence, by_sex = _parse_prevalence(raw.get("prevalence", {}))
    return ConditionSpec(
        id=raw["id"],
        code=code,
        prevalence_by_bracket=prevalence,
        prevalence_by_sex=by_sex,
    )


def load_module_from_str(yaml_text: str) -> Module:
    """Parse a module YAML string into a validated Module."""
    try:
        data = yaml.safe_load(yaml_text)
    except yaml.YAMLError as exc:
        raise ModuleError(f"invalid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise ModuleError("module must be a mapping at the top level")

    for required in ("module", "version", "conditions"):
        if required not in data:
            raise ModuleError(f"missing required key: {required}")

    cites = tuple(Citation(**c) for c in data.get("cites") or [])
    conditions = tuple(_parse_condition(c) for c in data["conditions"])

    return Module(
        name=str(data["module"]),
        version=str(data["version"]),
        description=str(data.get("description", "")),
        cites=cites,
        conditions=conditions,
    )


def load_module(name: str) -> Module:
    """Load a bundled module by name from parker_atlas.modules.library."""
    pkg = resources.files("parker_atlas.modules.library")
    target = pkg.joinpath(f"{name}.yaml")
    if not target.is_file():
        bundled = ", ".join(list_bundled_modules()) or "(none)"
        raise ModuleError(f"no bundled module named {name!r}. Available: {bundled}")
    return load_module_from_str(target.read_text(encoding="utf-8"))


def list_bundled_modules() -> list[str]:
    """Return sorted names of all bundled modules."""
    pkg = resources.files("parker_atlas.modules.library")
    return sorted(
        f.name.removesuffix(".yaml")
        for f in pkg.iterdir()
        if f.name.endswith(".yaml")
    )


# -- Execution ---------------------------------------------------------------


def _find_bracket(age: int, brackets) -> tuple[int, int] | None:
    for lo, hi in brackets:
        if lo <= age <= hi:
            return (lo, hi)
    return None


def _lookup_prevalence(
    cond: ConditionSpec, age: int, sex: str
) -> float | None:
    if cond.prevalence_by_sex is not None:
        brackets = cond.prevalence_by_sex.get(sex)
        if brackets is None:
            return None
        key = _find_bracket(age, brackets.keys())
        return brackets.get(key) if key else None
    key = _find_bracket(age, cond.prevalence_by_bracket.keys())
    return cond.prevalence_by_bracket.get(key) if key else None


def run_module(
    module: Module, age_years: int, sex: str, rng: random.Random
) -> list[Diagnosis]:
    """Run a probability module for one patient; return sampled diagnoses."""
    out: list[Diagnosis] = []
    for cond in module.conditions:
        p = _lookup_prevalence(cond, age_years, sex)
        if p is None:
            continue
        if rng.random() < p:
            out.append(Diagnosis(condition=cond))
    return out

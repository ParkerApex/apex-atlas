"""
Fidelity expectations — reference targets for the cohort-validation harness.

Each expectation file declares metrics (e.g. "essential_hypertension
prevalence by age bracket"), target values, and tolerances. The cohort
harness computes the corresponding aggregate statistics from generated
output and fails if any metric breaches its tolerance.

Expectations are independent of modules: a module declares *what rates
it samples at*, an expectation declares *what rates the output should
match in aggregate*. For first-cut modules these coincide (the
expectation mirrors the module's declared prevalence) — the harness is
therefore catching pipeline bugs, not calibration drift. When an
expectation cites an external source (NHANES, CDC BRFSS) and diverges
from the module's declared rates, the harness begins testing
calibration too.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
from typing import Any

import yaml


class ExpectationError(ValueError):
    """Raised when an expectation file is malformed or invalid."""


# Z critical values for symmetric two-sided CIs at the named confidence level.
Z_FOR_CONFIDENCE: dict[float, float] = {
    90.0: 1.6449,
    95.0: 1.9600,
    99.0: 2.5758,
    99.9: 3.2905,
}


@dataclass(frozen=True, slots=True)
class Tolerance:
    """
    Tolerance policy for a single metric.

    Kinds:
    - "absolute"  — fixed half-width in proportion units; requires `value`.
    - "normal"    — two-sided z-test under H0: true proportion = target. Uses
                    SE = sqrt(target*(1-target)/n). `confidence` selects z.
    - "wilson"    — Wilson score CI around the *observed* proportion;
                    passes if the target falls inside. Robust at extreme p.
    """

    kind: str
    value: float = 0.0          # absolute only
    confidence: float = 95.0    # normal / wilson only


SEX_STRATA = ("female", "male")


@dataclass(frozen=True, slots=True)
class Metric:
    id: str
    kind: str                     # "conditional_prevalence"
    condition_code: str           # terminology code (SNOMED/ICD-10/etc.)
    condition_system: str
    stratify_by: str              # "age_bracket" | "sex_and_age"
    tolerance: Tolerance
    # For stratify_by="age_bracket": `targets` holds {bracket: rate}.
    # For stratify_by="sex_and_age": `targets` is empty and
    # `targets_by_sex` holds {sex: {bracket: rate}}.
    targets: dict[tuple[int, int], float]
    targets_by_sex: dict[str, dict[tuple[int, int], float]] | None = None


PROVENANCE_LEVELS = ("placeholder", "sourced", "verified")


@dataclass(frozen=True, slots=True)
class SourceCitation:
    """One external publication / dataset backing an expectation."""

    source: str
    url: str = ""
    table: str = ""      # e.g. "Table 4" or a PUMS query description
    version: str = ""    # e.g. "NHANES 2017-2020 age-adjusted"
    accessed: str = ""   # ISO date string when the number was last verified
    note: str = ""


@dataclass(frozen=True, slots=True)
class ExpectationSource:
    name: str
    url: str = ""
    note: str = ""
    # Provenance tiers:
    #   placeholder → curated approximation, NOT sourced from a public dataset;
    #                 output must not be cited as reflecting that dataset.
    #   sourced     → targets come from publicly-cited data, but numbers
    #                 haven't been independently re-verified by the project.
    #   verified    → numbers re-computed from public microdata by the
    #                 project and matched against the citation within tolerance.
    provenance: str = "placeholder"
    citations: tuple[SourceCitation, ...] = ()


@dataclass(frozen=True, slots=True)
class Expectation:
    module: str
    version: str
    source: ExpectationSource
    metrics: tuple[Metric, ...]


def _parse_tolerance(raw: dict[str, Any]) -> Tolerance:
    if not isinstance(raw, dict) or "kind" not in raw:
        raise ExpectationError("tolerance requires a mapping with 'kind'")
    kind = str(raw["kind"])
    if kind == "absolute":
        if "value" not in raw:
            raise ExpectationError("tolerance kind 'absolute' requires 'value'")
        return Tolerance(kind="absolute", value=float(raw["value"]))
    if kind in ("normal", "wilson"):
        confidence = float(raw.get("confidence", 95.0))
        if confidence not in Z_FOR_CONFIDENCE:
            raise ExpectationError(
                f"unsupported confidence {confidence!r}; "
                f"choices: {sorted(Z_FOR_CONFIDENCE)}"
            )
        return Tolerance(kind=kind, confidence=confidence)
    raise ExpectationError(
        f"unsupported tolerance kind {kind!r}; choices: absolute, normal, wilson"
    )


def _parse_bracket(s: str) -> tuple[int, int]:
    try:
        lo_str, hi_str = s.split("-")
        return int(lo_str), int(hi_str)
    except ValueError as exc:
        raise ExpectationError(f"invalid bracket {s!r}; expected 'LOW-HIGH'") from exc


def _parse_metric(raw: dict[str, Any]) -> Metric:
    for required in ("id", "kind", "condition_code", "stratify_by", "tolerance", "targets"):
        if required not in raw:
            raise ExpectationError(f"metric missing required key: {required}")

    tolerance = _parse_tolerance(raw["tolerance"])

    if raw["kind"] != "conditional_prevalence":
        raise ExpectationError(
            f"unsupported metric kind {raw['kind']!r}; only 'conditional_prevalence' is implemented"
        )
    stratify_by = str(raw["stratify_by"])
    if stratify_by not in ("age_bracket", "sex_and_age"):
        raise ExpectationError(
            f"unsupported stratification {stratify_by!r}; "
            f"choices: age_bracket, sex_and_age"
        )

    targets: dict[tuple[int, int], float] = {}
    targets_by_sex: dict[str, dict[tuple[int, int], float]] | None = None

    if stratify_by == "age_bracket":
        targets = {_parse_bracket(k): float(v) for k, v in raw["targets"].items()}
    else:  # sex_and_age
        raw_targets = raw["targets"]
        if not isinstance(raw_targets, dict):
            raise ExpectationError(
                f"{raw.get('id')!r}: sex_and_age targets must be a mapping of sex → brackets"
            )
        bad_keys = set(raw_targets) - set(SEX_STRATA)
        if bad_keys:
            raise ExpectationError(
                f"{raw.get('id')!r}: sex_and_age targets has unknown sex keys {sorted(bad_keys)}; "
                f"choices: {list(SEX_STRATA)}"
            )
        targets_by_sex = {
            sex: {_parse_bracket(k): float(v) for k, v in brackets.items()}
            for sex, brackets in raw_targets.items()
        }

    return Metric(
        id=str(raw["id"]),
        kind=str(raw["kind"]),
        condition_code=str(raw["condition_code"]),
        condition_system=str(raw.get("condition_system", "")),
        stratify_by=stratify_by,
        tolerance=tolerance,
        targets=targets,
        targets_by_sex=targets_by_sex,
    )


def load_expectation_from_str(yaml_text: str) -> Expectation:
    try:
        data = yaml.safe_load(yaml_text)
    except yaml.YAMLError as exc:
        raise ExpectationError(f"invalid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise ExpectationError("expectation must be a mapping at the top level")
    for required in ("module", "version", "metrics"):
        if required not in data:
            raise ExpectationError(f"missing required key: {required}")

    src_raw = data.get("source") or {}
    provenance = str(src_raw.get("provenance", "placeholder"))
    if provenance not in PROVENANCE_LEVELS:
        raise ExpectationError(
            f"unsupported provenance {provenance!r}; "
            f"choices: {list(PROVENANCE_LEVELS)}"
        )
    citations_raw = src_raw.get("citations") or []
    citations = tuple(
        SourceCitation(
            source=str(c.get("source", "")),
            url=str(c.get("url", "")),
            table=str(c.get("table", "")),
            version=str(c.get("version", "")),
            accessed=str(c.get("accessed", "")),
            note=str(c.get("note", "")),
        )
        for c in citations_raw
    )
    source = ExpectationSource(
        name=str(src_raw.get("name", "")),
        url=str(src_raw.get("url", "")),
        note=str(src_raw.get("note", "")),
        provenance=provenance,
        citations=citations,
    )

    metrics = tuple(_parse_metric(m) for m in data["metrics"])
    return Expectation(
        module=str(data["module"]),
        version=str(data["version"]),
        source=source,
        metrics=metrics,
    )


def load_bundled_expectation(module: str) -> Expectation:
    """Load a bundled expectation by module name."""
    pkg = resources.files("parker_atlas.validation.expectations.library")
    target = pkg.joinpath(f"{module}.yaml")
    if not target.is_file():
        available = ", ".join(list_bundled_expectations()) or "(none)"
        raise ExpectationError(
            f"no bundled expectation for module {module!r}. Available: {available}"
        )
    return load_expectation_from_str(target.read_text(encoding="utf-8"))


def list_bundled_expectations() -> list[str]:
    pkg = resources.files("parker_atlas.validation.expectations.library")
    return sorted(
        f.name.removesuffix(".yaml")
        for f in pkg.iterdir()
        if f.name.endswith(".yaml")
    )

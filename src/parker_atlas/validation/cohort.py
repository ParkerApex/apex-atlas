"""
Cohort fidelity harness.

Given a directory of generated FHIR R4 Bundle JSON files and an
`Expectation`, compute each declared metric over the cohort and check
it against the target within tolerance.

Current scope (first cut):
- Metric kind: `conditional_prevalence` — prevalence of a specific
  Condition coded with a particular SNOMED/ICD-10 code.
- Stratification: `age_bracket` — inclusive `(low, high)` buckets.
- Tolerance: `absolute` — `|actual - target| <= value`.
- `--min-samples` floor: brackets below this N are skipped (with a
  notice in the report) so small-N sampling variance doesn't drive
  false failures.

Later extensions: confidence-interval-aware tolerance, sex/race
stratification, joint metrics, Observation-value distributions.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from parker_atlas.validation.expectations import (
    Expectation,
    Metric,
    Tolerance,
    Z_FOR_CONFIDENCE,
)


@dataclass(frozen=True, slots=True)
class MetricResult:
    metric_id: str
    bracket: tuple[int, int]
    n: int
    actual: float
    target: float
    tolerance: float
    within_tolerance: bool


@dataclass
class CohortReport:
    total_patients: int
    bundles_scanned: int
    results: list[MetricResult] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    parse_errors: list[tuple[Path, str]] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """True iff no metric exceeded its tolerance."""
        return all(r.within_tolerance for r in self.results) and not self.parse_errors

    @property
    def failing_metrics(self) -> list[MetricResult]:
        return [r for r in self.results if not r.within_tolerance]


def _age_years(birth_date_str: str, reference: date) -> int:
    birth = date.fromisoformat(birth_date_str)
    return (reference - birth).days // 365


def _find_bracket(
    age: int, brackets: tuple[tuple[int, int], ...]
) -> tuple[int, int] | None:
    for lo, hi in brackets:
        if lo <= age <= hi:
            return (lo, hi)
    return None


def _extract_patient_and_conditions(
    bundle: dict[str, Any],
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    patient: dict[str, Any] | None = None
    conditions: list[dict[str, Any]] = []
    for entry in bundle.get("entry", []) or []:
        res = entry.get("resource") or {}
        rtype = res.get("resourceType")
        if rtype == "Patient" and patient is None:
            patient = res
        elif rtype == "Condition":
            conditions.append(res)
    return patient, conditions


def _condition_codes(conditions: list[dict[str, Any]]) -> set[str]:
    codes: set[str] = set()
    for cond in conditions:
        for coding in (cond.get("code") or {}).get("coding", []) or []:
            code = coding.get("code")
            if code:
                codes.add(code)
    return codes


def _load_cohort(
    path: Path, report: CohortReport, reference_date: date
) -> list[tuple[int, set[str]]]:
    """Return (age, set_of_condition_codes) per patient. Mutates report."""
    files = sorted(path.rglob("*.json")) if path.is_dir() else [path]
    patients: list[tuple[int, set[str]]] = []
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            report.parse_errors.append((f, str(exc)))
            continue
        if data.get("resourceType") != "Bundle":
            # Structural validator is the right tool for non-Bundle shapes.
            continue
        report.bundles_scanned += 1
        patient, conditions = _extract_patient_and_conditions(data)
        if patient is None or "birthDate" not in patient:
            continue
        age = _age_years(patient["birthDate"], reference_date)
        patients.append((age, _condition_codes(conditions)))
    report.total_patients = len(patients)
    return patients


def _check_tolerance(
    tol: Tolerance, actual: float, target: float, n: int
) -> tuple[bool, float]:
    """
    Evaluate whether `actual` meets `target` under `tol` at sample size `n`.
    Returns (within_tolerance, effective_half_width). The half-width is:
    - `tol.value` for `absolute`;
    - `z * SE(target)` for `normal`;
    - the Wilson CI radius (around observed) for `wilson`.
    """
    if tol.kind == "absolute":
        return abs(actual - target) <= tol.value, tol.value

    z = Z_FOR_CONFIDENCE[tol.confidence]

    if tol.kind == "normal":
        if target <= 0.0 or target >= 1.0:
            # Degenerate: only exact match passes.
            return actual == target, 0.0
        se = math.sqrt(target * (1.0 - target) / n)
        half = z * se
        return abs(actual - target) <= half, half

    if tol.kind == "wilson":
        if n == 0:
            return False, 0.0
        denom = 1.0 + z * z / n
        center = (actual + z * z / (2.0 * n)) / denom
        radius = (z / denom) * math.sqrt(
            actual * (1.0 - actual) / n + z * z / (4.0 * n * n)
        )
        return (center - radius) <= target <= (center + radius), radius

    raise ValueError(f"unknown tolerance kind {tol.kind!r}")


def _evaluate_metric(
    metric: Metric,
    patients: list[tuple[int, set[str]]],
    *,
    min_samples: int,
    report: CohortReport,
) -> None:
    if metric.kind != "conditional_prevalence":
        report.skipped.append(f"{metric.id}: unsupported kind {metric.kind!r}")
        return
    if metric.stratify_by != "age_bracket":
        report.skipped.append(
            f"{metric.id}: unsupported stratification {metric.stratify_by!r}"
        )
        return

    buckets: dict[tuple[int, int], list[bool]] = defaultdict(list)
    bracket_keys = tuple(metric.targets.keys())
    for age, codes in patients:
        bracket = _find_bracket(age, bracket_keys)
        if bracket is None:
            continue
        buckets[bracket].append(metric.condition_code in codes)

    for bracket, target in metric.targets.items():
        samples = buckets.get(bracket, [])
        n = len(samples)
        if n < min_samples:
            report.skipped.append(
                f"{metric.id} {bracket[0]}-{bracket[1]}: "
                f"N={n} < min_samples ({min_samples})"
            )
            continue
        actual = sum(samples) / n
        within, half = _check_tolerance(metric.tolerance, actual, target, n)
        report.results.append(
            MetricResult(
                metric_id=metric.id,
                bracket=bracket,
                n=n,
                actual=actual,
                target=target,
                tolerance=half,
                within_tolerance=within,
            )
        )


def evaluate_cohort(
    path: Path,
    expectation: Expectation,
    *,
    min_samples: int = 30,
    reference_date: date | None = None,
) -> CohortReport:
    """Run `expectation` over the cohort rooted at `path` and return a report."""
    reference = reference_date or date.today()
    report = CohortReport(total_patients=0, bundles_scanned=0)
    patients = _load_cohort(path, report, reference)
    for metric in expectation.metrics:
        _evaluate_metric(metric, patients, min_samples=min_samples, report=report)
    return report

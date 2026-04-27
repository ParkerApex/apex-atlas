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
import uuid
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
    bracket: tuple[int, int] | None  # None when stratify_by="cohort"
    sex: str | None                  # None unless stratify_by="sex_and_age"
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


def _extract_patient_and_resources(
    bundle: dict[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, list[dict[str, Any]]]]:
    """Return (Patient, dict mapping resourceType → list of resources)."""
    patient: dict[str, Any] | None = None
    by_type: dict[str, list[dict[str, Any]]] = {}
    for entry in bundle.get("entry", []) or []:
        res = entry.get("resource") or {}
        rtype = res.get("resourceType")
        if rtype is None:
            continue
        if rtype == "Patient" and patient is None:
            patient = res
        by_type.setdefault(rtype, []).append(res)
    return patient, by_type


def _resource_codes(resource: dict[str, Any]) -> set[str]:
    """Return the set of terminology codes identifying this resource."""
    rtype = resource.get("resourceType")
    codes: set[str] = set()
    if rtype in ("Condition", "Observation", "Procedure"):
        for coding in (resource.get("code") or {}).get("coding", []) or []:
            if coding.get("code"):
                codes.add(coding["code"])
    elif rtype == "MedicationRequest":
        med = resource.get("medicationCodeableConcept") or {}
        for coding in med.get("coding", []) or []:
            if coding.get("code"):
                codes.add(coding["code"])
    elif rtype == "Encounter":
        for type_entry in resource.get("type") or []:
            for coding in (type_entry or {}).get("coding", []) or []:
                if coding.get("code"):
                    codes.add(coding["code"])
    return codes


def _codes_by_type(by_type: dict[str, list[dict[str, Any]]]) -> dict[str, set[str]]:
    """Aggregate codes per resource type for one patient."""
    out: dict[str, set[str]] = {}
    for rtype, resources in by_type.items():
        codes: set[str] = set()
        for res in resources:
            codes.update(_resource_codes(res))
        out[rtype] = codes
    return out


# Same URL namespace fhir/bundle.py uses to mint per-Patient fullUrls.
_URL_NAMESPACE = uuid.UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8")


def _load_cohort_bundles(
    path: Path, report: CohortReport, reference_date: date
) -> list[tuple[int, str, set[str], dict[str, set[str]]]]:
    files = sorted(path.rglob("*.json")) if path.is_dir() else [path]
    patients: list[tuple[int, str, set[str], dict[str, set[str]]]] = []
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
        patient, by_type = _extract_patient_and_resources(data)
        if patient is None or "birthDate" not in patient:
            continue
        age = _age_years(patient["birthDate"], reference_date)
        sex = str(patient.get("gender", ""))
        codes_by_type = _codes_by_type(by_type)
        condition_codes = codes_by_type.get("Condition", set())
        patients.append((age, sex, condition_codes, codes_by_type))
    return patients


def _load_cohort_ndjson(
    path: Path, report: CohortReport, reference_date: date
) -> list[tuple[int, str, set[str], dict[str, set[str]]]]:
    """Read NDJSON output (one file per resourceType) and group by Patient.

    Patient.ndjson is the spine. Each Patient.id is the GPX string;
    Atlas's bundle writer used `urn:uuid:<uuid5(URL_NAMESPACE, gpx)>` as
    the per-Patient fullUrl, and other resources reference that fullUrl
    via subject.reference. We rebuild the same urn:uuid mapping here
    from each Patient.id so the cohort harness can group resources back
    to their owners.
    """
    patient_file = path / "Patient.ndjson"
    if not patient_file.is_file():
        return []

    patient_by_url: dict[str, dict[str, Any]] = {}
    for lineno, line in enumerate(
        patient_file.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        try:
            patient = json.loads(line)
        except json.JSONDecodeError as exc:
            report.parse_errors.append(
                (patient_file, f"line {lineno}: {exc}")
            )
            continue
        if "id" not in patient:
            continue
        url = f"urn:uuid:{uuid.uuid5(_URL_NAMESPACE, str(patient['id']))}"
        patient_by_url[url] = patient
    report.bundles_scanned = len(patient_by_url)

    codes_by_patient: dict[str, dict[str, set[str]]] = {
        url: {} for url in patient_by_url
    }
    for f in sorted(path.glob("*.ndjson")):
        if f.stem == "Patient":
            continue
        for lineno, line in enumerate(
            f.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if not line.strip():
                continue
            try:
                resource = json.loads(line)
            except json.JSONDecodeError as exc:
                report.parse_errors.append((f, f"line {lineno}: {exc}"))
                continue
            ref = (resource.get("subject") or {}).get("reference", "")
            if ref not in patient_by_url:
                continue  # orphan resource — silently skipped
            rtype = resource.get("resourceType", "")
            bucket = codes_by_patient[ref].setdefault(rtype, set())
            bucket.update(_resource_codes(resource))

    patients: list[tuple[int, str, set[str], dict[str, set[str]]]] = []
    for url, patient in patient_by_url.items():
        if "birthDate" not in patient:
            continue
        age = _age_years(patient["birthDate"], reference_date)
        sex = str(patient.get("gender", ""))
        codes_by_type = codes_by_patient[url]
        condition_codes = codes_by_type.get("Condition", set())
        patients.append((age, sex, condition_codes, codes_by_type))
    return patients


def _load_cohort(
    path: Path, report: CohortReport, reference_date: date
) -> list[tuple[int, str, set[str], dict[str, set[str]]]]:
    """Dispatch to the bundle or NDJSON loader based on what's at `path`.

    `codes_by_resource_type` lets the harness check emit-presence metrics —
    e.g., "of patients with this Condition, how many have a MedicationRequest
    of this RxNorm code?"
    """
    if path.is_dir() and (path / "Patient.ndjson").exists():
        patients = _load_cohort_ndjson(path, report, reference_date)
    else:
        patients = _load_cohort_bundles(path, report, reference_date)
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


def _record_prevalence(
    *,
    metric: Metric,
    bracket: tuple[int, int],
    sex: str | None,
    samples: list[bool],
    min_samples: int,
    target: float,
    report: CohortReport,
) -> None:
    n = len(samples)
    sex_label = f" {sex}" if sex else ""
    if n < min_samples:
        report.skipped.append(
            f"{metric.id} {bracket[0]}-{bracket[1]}{sex_label}: "
            f"N={n} < min_samples ({min_samples})"
        )
        return
    actual = sum(samples) / n
    within, half = _check_tolerance(metric.tolerance, actual, target, n)
    report.results.append(
        MetricResult(
            metric_id=metric.id,
            bracket=bracket,
            sex=sex,
            n=n,
            actual=actual,
            target=target,
            tolerance=half,
            within_tolerance=within,
        )
    )


def _evaluate_emit_presence(
    metric: Metric,
    patients: list[tuple[int, str, set[str], dict[str, set[str]]]],
    *,
    min_samples: int,
    report: CohortReport,
) -> None:
    assert metric.emit_presence is not None and metric.target is not None
    presence = metric.emit_presence
    target = metric.target

    has_emit: list[bool] = []
    for _age, _sex, condition_codes, codes_by_type in patients:
        if metric.condition_code not in condition_codes:
            continue
        codes_for_type = codes_by_type.get(presence.resource_type, set())
        if presence.code is None:
            has_emit.append(len(codes_for_type) > 0)
        else:
            has_emit.append(presence.code in codes_for_type)

    n = len(has_emit)
    if n < min_samples:
        report.skipped.append(
            f"{metric.id}: N={n} patients with condition < min_samples ({min_samples})"
        )
        return
    actual = sum(has_emit) / n
    within, half = _check_tolerance(metric.tolerance, actual, target, n)
    report.results.append(
        MetricResult(
            metric_id=metric.id,
            bracket=None,
            sex=None,
            n=n,
            actual=actual,
            target=target,
            tolerance=half,
            within_tolerance=within,
        )
    )


def _evaluate_metric(
    metric: Metric,
    patients: list[tuple[int, str, set[str], dict[str, set[str]]]],
    *,
    min_samples: int,
    report: CohortReport,
) -> None:
    if metric.kind == "emit_presence_rate":
        _evaluate_emit_presence(metric, patients, min_samples=min_samples, report=report)
        return
    if metric.kind != "conditional_prevalence":
        report.skipped.append(f"{metric.id}: unsupported kind {metric.kind!r}")
        return

    if metric.stratify_by == "age_bracket":
        buckets: dict[tuple[int, int], list[bool]] = defaultdict(list)
        bracket_keys = tuple(metric.targets.keys())
        for age, _sex, codes, _by_type in patients:
            bracket = _find_bracket(age, bracket_keys)
            if bracket is None:
                continue
            buckets[bracket].append(metric.condition_code in codes)
        for bracket, target in metric.targets.items():
            _record_prevalence(
                metric=metric,
                bracket=bracket,
                sex=None,
                samples=buckets.get(bracket, []),
                min_samples=min_samples,
                target=target,
                report=report,
            )
        return

    if metric.stratify_by == "sex_and_age":
        assert metric.targets_by_sex is not None
        sex_buckets: dict[str, dict[tuple[int, int], list[bool]]] = {
            sex: defaultdict(list) for sex in metric.targets_by_sex
        }
        for sex, brackets in metric.targets_by_sex.items():
            bracket_keys = tuple(brackets.keys())
            for age, p_sex, codes, _by_type in patients:
                if p_sex != sex:
                    continue
                bracket = _find_bracket(age, bracket_keys)
                if bracket is None:
                    continue
                sex_buckets[sex][bracket].append(metric.condition_code in codes)
        for sex, brackets in metric.targets_by_sex.items():
            for bracket, target in brackets.items():
                _record_prevalence(
                    metric=metric,
                    bracket=bracket,
                    sex=sex,
                    samples=sex_buckets[sex].get(bracket, []),
                    min_samples=min_samples,
                    target=target,
                    report=report,
                )
        return

    report.skipped.append(
        f"{metric.id}: unsupported stratification {metric.stratify_by!r}"
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

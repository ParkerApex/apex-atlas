"""
FHIR R4 MeasureReport resource construction.

Supports two MeasureReport types:
- `individual`: one per patient, captures denominator/numerator membership
  and a 0.0/1.0 measureScore for each population group.
- `summary`: one per measure for the whole cohort, with aggregate
  denominator/numerator counts and a population-level measureScore.

Measure canonical URLs follow the pattern:
  https://parkerapex.com/fhir/Measure/<measure-id>

This is the only synthetic FHIR data generator that produces MeasureReport
resources alongside patient records, enabling payers and health systems to
use Atlas populations directly in quality measure testing pipelines.

Measure groups follow the HL7 DEQM (Data Exchange for Quality Measures)
Individual MeasureReport profile:
  http://hl7.org/fhir/us/davinci-deqm/StructureDefinition/indv-measurereport-deqm

Population code system:
  http://terminology.hl7.org/CodeSystem/measure-population
  codes: initial-population, denominator, denominator-exclusion, numerator
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from parker_atlas.gpx import GPX

_URL_NAMESPACE = uuid.UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8")

MEASURE_BASE_URL = "https://parkerapex.com/fhir/Measure"

_POP_CODE_SYSTEM = (
    "http://terminology.hl7.org/CodeSystem/measure-population"
)
_DEQM_INDV_PROFILE = (
    "http://hl7.org/fhir/us/davinci-deqm/StructureDefinition/"
    "indv-measurereport-deqm"
)
_DEQM_SUMMARY_PROFILE = (
    "http://hl7.org/fhir/us/davinci-deqm/StructureDefinition/"
    "summary-measurereport-deqm"
)


def _report_id(gpx: GPX, measure_id: str) -> str:
    return str(uuid.uuid5(_URL_NAMESPACE, f"{gpx}:measurereport:{measure_id}"))


def _summary_report_id(measure_id: str, period_end: date) -> str:
    return str(
        uuid.uuid5(_URL_NAMESPACE, f"summary:measurereport:{measure_id}:{period_end.isoformat()}")
    )


def _pop_element(code: str, display: str, count: int) -> dict[str, Any]:
    return {
        "code": {
            "coding": [
                {
                    "system": _POP_CODE_SYSTEM,
                    "code": code,
                    "display": display,
                }
            ]
        },
        "count": count,
    }


def build_individual_measure_report(
    gpx: GPX,
    patient_fullurl: str,
    measure_id: str,
    measure_title: str,
    *,
    in_initial_population: bool,
    in_denominator: bool,
    in_numerator: bool,
    period_start: date,
    period_end: date,
) -> dict[str, Any]:
    """Build a DEQM Individual MeasureReport for one patient.

    Args:
        gpx: patient GPX identifier.
        patient_fullurl: Bundle fullUrl of the Patient resource.
        measure_id: short measure identifier (e.g. "DM-HbA1c").
        measure_title: human-readable measure name.
        in_initial_population: True if the patient meets the initial
            population criteria (e.g., has the target condition).
        in_denominator: True if the patient is in the denominator
            (subset of initial population who are eligible).
        in_numerator: True if the patient meets the numerator criteria
            (denominator patient who received the indicated care).
        period_start: start of the measurement period (typically Jan 1).
        period_end: end of the measurement period (typically Dec 31).
    """
    measure_score = None
    if in_denominator:
        measure_score = {"value": 1.0 if in_numerator else 0.0, "unit": "1"}

    resource: dict[str, Any] = {
        "resourceType": "MeasureReport",
        "id": _report_id(gpx, measure_id),
        "meta": {
            "profile": [_DEQM_INDV_PROFILE],
            "tag": [GPX.synthetic_meta_tag()],
        },
        "status": "complete",
        "type": "individual",
        "measure": f"{MEASURE_BASE_URL}/{measure_id}",
        "subject": {"reference": patient_fullurl},
        "date": period_end.isoformat(),
        "period": {
            "start": period_start.isoformat(),
            "end": period_end.isoformat(),
        },
        "group": [
            {
                "population": [
                    _pop_element(
                        "initial-population",
                        "Initial Population",
                        1 if in_initial_population else 0,
                    ),
                    _pop_element(
                        "denominator",
                        "Denominator",
                        1 if in_denominator else 0,
                    ),
                    _pop_element(
                        "numerator",
                        "Numerator",
                        1 if in_numerator else 0,
                    ),
                ],
            }
        ],
    }
    if measure_score is not None:
        resource["group"][0]["measureScore"] = measure_score
    return resource


def build_summary_measure_report(
    measure_id: str,
    measure_title: str,
    *,
    initial_population_count: int,
    denominator_count: int,
    numerator_count: int,
    period_start: date,
    period_end: date,
) -> dict[str, Any]:
    """Build a DEQM Summary MeasureReport for the whole cohort.

    The summary report has no `subject` (it covers the full population)
    and carries aggregate counts with a population-level measureScore.
    Written once per measure at the end of `atlas generate`.

    Args:
        measure_id: short measure identifier.
        measure_title: human-readable measure name.
        initial_population_count: patients in initial population.
        denominator_count: patients in denominator.
        numerator_count: patients in numerator.
        period_start: start of the measurement period.
        period_end: end of the measurement period.
    """
    measure_score_value = (
        numerator_count / denominator_count if denominator_count > 0 else 0.0
    )

    return {
        "resourceType": "MeasureReport",
        "id": _summary_report_id(measure_id, period_end),
        "meta": {
            "profile": [_DEQM_SUMMARY_PROFILE],
            "tag": [GPX.synthetic_meta_tag()],
        },
        "status": "complete",
        "type": "summary",
        "measure": f"{MEASURE_BASE_URL}/{measure_id}",
        "date": period_end.isoformat(),
        "period": {
            "start": period_start.isoformat(),
            "end": period_end.isoformat(),
        },
        "group": [
            {
                "population": [
                    _pop_element(
                        "initial-population",
                        "Initial Population",
                        initial_population_count,
                    ),
                    _pop_element(
                        "denominator",
                        "Denominator",
                        denominator_count,
                    ),
                    _pop_element(
                        "numerator",
                        "Numerator",
                        numerator_count,
                    ),
                ],
                "measureScore": {
                    "value": round(measure_score_value, 4),
                    "unit": "1",
                },
            }
        ],
    }

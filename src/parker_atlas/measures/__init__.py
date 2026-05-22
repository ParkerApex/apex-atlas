"""
APEX Atlas clinical quality measures.

Defines HEDIS-analog quality measures that can be evaluated against
generated patient bundles. Each measure has:
- A unique short ID (used in MeasureReport.measure canonical URL)
- A human-readable title
- Denominator logic: which patients are eligible (based on conditions/resources)
- Numerator logic: which eligible patients received the indicated care

Measures are evaluated at the end of atlas generate when --with-measures
is passed. Each patient gets an individual MeasureReport per applicable
measure; a summary MeasureReport is also written for the full cohort.

Implemented measures:
  DM-HbA1c     — Diabetics with HbA1c test in the measurement period
  HTN-BPControl — Hypertensives with controlled BP (<140/90) in period
  PreventiveCare — Adults with a wellness visit in the measurement period
  FluVaccine    — Adults with seasonal influenza immunization in period
  PedWellChild  — Children (0-17) with well-child visit in period
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class MeasureResult:
    """Evaluation result for one measure for one patient."""

    measure_id: str
    in_initial_population: bool
    in_denominator: bool
    in_numerator: bool


@dataclass
class MeasureTally:
    """Running count for one measure across all patients."""

    measure_id: str
    measure_title: str
    initial_population: int = 0
    denominator: int = 0
    numerator: int = 0

    def add(self, result: MeasureResult) -> None:
        if result.in_initial_population:
            self.initial_population += 1
        if result.in_denominator:
            self.denominator += 1
        if result.in_numerator:
            self.numerator += 1

    @property
    def rate(self) -> float:
        return self.numerator / self.denominator if self.denominator else 0.0


# LOINC codes used to detect numerator satisfaction in generated resources.
_HBAIC_LOINCS = {"4548-4", "17856-6", "59261-8"}
_BP_PANEL_LOINC = "85354-9"
_WELLNESS_SNOMED = {"162673000", "185349003", "410620009"}
_FLU_CVX = {"140", "141", "144", "149", "150", "153", "155", "158", "161", "166", "171"}
_WELL_CHILD_SNOMED = {"170149006", "410620009"}

# ICD-10 / SNOMED codes that mark a patient as having each target condition.
_DIABETES_SNOMED = {
    "44054006",   # T2DM
    "73211009",   # DM (general)
    "314893005",  # T2DM with renal complication
}
_HTN_SNOMED = {
    "59621000",   # Essential hypertension
    "38341003",   # HTN (general)
}


def _has_condition(resources: list[dict[str, Any]], snomed_codes: set[str]) -> bool:
    for r in resources:
        if r.get("resourceType") != "Condition":
            continue
        for coding in r.get("code", {}).get("coding", []):
            if coding.get("code") in snomed_codes:
                return True
    return False


def _has_observation_loinc(resources: list[dict[str, Any]], loinc_codes: set[str]) -> bool:
    for r in resources:
        if r.get("resourceType") != "Observation":
            continue
        for coding in r.get("code", {}).get("coding", []):
            if coding.get("code") in loinc_codes:
                return True
    return False


def _has_bp_controlled(resources: list[dict[str, Any]]) -> bool:
    """True if any BP observation has systolic <140 AND diastolic <90."""
    for r in resources:
        if r.get("resourceType") != "Observation":
            continue
        is_bp = any(
            c.get("code") == _BP_PANEL_LOINC
            for c in r.get("code", {}).get("coding", [])
        )
        if not is_bp:
            continue
        sbp = dbp = None
        for comp in r.get("component", []):
            code = next(
                (c.get("code") for c in comp.get("code", {}).get("coding", [])), None
            )
            val = comp.get("valueQuantity", {}).get("value")
            if code == "8480-6":
                sbp = val
            elif code == "8462-4":
                dbp = val
        if sbp is not None and dbp is not None:
            if sbp < 140 and dbp < 90:
                return True
    return False


def _has_wellness_encounter(resources: list[dict[str, Any]]) -> bool:
    for r in resources:
        if r.get("resourceType") != "Encounter":
            continue
        for coding in r.get("type", [{}])[0].get("coding", []) if r.get("type") else []:
            if coding.get("code") in _WELLNESS_SNOMED:
                return True
    return False


def _has_flu_immunization(resources: list[dict[str, Any]]) -> bool:
    for r in resources:
        if r.get("resourceType") != "Immunization":
            continue
        for coding in r.get("vaccineCode", {}).get("coding", []):
            if coding.get("code") in _FLU_CVX:
                return True
    return False


def _has_well_child_encounter(resources: list[dict[str, Any]]) -> bool:
    for r in resources:
        if r.get("resourceType") != "Encounter":
            continue
        for type_entry in r.get("type", []):
            for coding in type_entry.get("coding", []):
                if coding.get("code") in _WELL_CHILD_SNOMED:
                    return True
    return False


def evaluate_measures(
    age_years: int,
    sex: str,
    resources: list[dict[str, Any]],
) -> list[MeasureResult]:
    """Evaluate all measures for one patient.

    Args:
        age_years: patient's current age in years.
        sex: "female" | "male".
        resources: flat list of all FHIR resources in the patient's bundle
            (Patient resource excluded — caller handles that).

    Returns:
        A list of MeasureResult, one per measure evaluated.
    """
    results: list[MeasureResult] = []

    # DM-HbA1c: diabetics (18+) who had an HbA1c test this period
    is_adult = age_years >= 18
    has_diabetes = _has_condition(resources, _DIABETES_SNOMED)
    in_dm_denom = is_adult and has_diabetes
    results.append(
        MeasureResult(
            measure_id="DM-HbA1c",
            in_initial_population=has_diabetes,
            in_denominator=in_dm_denom,
            in_numerator=in_dm_denom and _has_observation_loinc(resources, _HBAIC_LOINCS),
        )
    )

    # HTN-BPControl: hypertensives (18-85) with controlled BP this period
    has_htn = _has_condition(resources, _HTN_SNOMED)
    in_htn_denom = is_adult and age_years <= 85 and has_htn
    results.append(
        MeasureResult(
            measure_id="HTN-BPControl",
            in_initial_population=has_htn,
            in_denominator=in_htn_denom,
            in_numerator=in_htn_denom and _has_bp_controlled(resources),
        )
    )

    # PreventiveCare: adults (18-75) with a wellness visit this period
    in_prev_denom = 18 <= age_years <= 75
    results.append(
        MeasureResult(
            measure_id="PreventiveCare",
            in_initial_population=is_adult,
            in_denominator=in_prev_denom,
            in_numerator=in_prev_denom and _has_wellness_encounter(resources),
        )
    )

    # FluVaccine: all patients 6+ months who received seasonal flu vaccine
    in_flu_denom = age_years >= 1  # module fires for 1+ year-olds in practice
    results.append(
        MeasureResult(
            measure_id="FluVaccine",
            in_initial_population=in_flu_denom,
            in_denominator=in_flu_denom,
            in_numerator=in_flu_denom and _has_flu_immunization(resources),
        )
    )

    # PedWellChild: children 0-17 with a well-child visit this period
    is_child = age_years <= 17
    results.append(
        MeasureResult(
            measure_id="PedWellChild",
            in_initial_population=is_child,
            in_denominator=is_child,
            in_numerator=is_child and _has_well_child_encounter(resources),
        )
    )

    return results


MEASURE_TITLES: dict[str, str] = {
    "DM-HbA1c": "Diabetes: HbA1c Testing",
    "HTN-BPControl": "Hypertension: Blood Pressure Control",
    "PreventiveCare": "Preventive Care Visit (Adults)",
    "FluVaccine": "Influenza Immunization",
    "PedWellChild": "Well-Child Visit (Ages 0-17)",
}

ALL_MEASURE_IDS = list(MEASURE_TITLES.keys())

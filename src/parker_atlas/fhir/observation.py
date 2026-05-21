"""
FHIR R4 Observation resource construction.

Handles the two common shapes APEX Atlas modules need:

- **Single-value** (`value` kwarg): a simple lab result or vital sign with
  one measured Quantity. Used for A1C, total cholesterol, weight, etc.
- **Multi-component** (`components` kwarg): an Observation that groups
  several named measurements under one resource, most importantly
  blood pressure (systolic + diastolic as two components).

Every Observation carries:
- `subject.reference` pointing at the Patient's Bundle fullUrl
- An `effectiveDateTime` describing when the measurement was taken
- The HL7 HTEST meta tag marking the data as synthetic
- A claim of the appropriate US Core 6.1 profile (vital-signs,
  blood pressure, or laboratory result)

Callers pick the profile via `profile_url`; sensible defaults are
derived from `category` and the Observation code.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from fhir.resources.R4B.observation import Observation as _Observation

from parker_atlas.fhir._datetime import fhir_datetime
from parker_atlas.gpx import GPX
from parker_atlas.modules.runtime import Coding

OBSERVATION_CATEGORY_SYSTEM = (
    "http://terminology.hl7.org/CodeSystem/observation-category"
)
UCUM_SYSTEM = "http://unitsofmeasure.org"

US_CORE_PROFILE_BASE = "http://hl7.org/fhir/us/core/StructureDefinition"
US_CORE_VITAL_SIGNS_PROFILE = f"{US_CORE_PROFILE_BASE}/us-core-vital-signs|6.1.0"
US_CORE_BLOOD_PRESSURE_PROFILE = f"{US_CORE_PROFILE_BASE}/us-core-blood-pressure|6.1.0"
US_CORE_LAB_RESULT_PROFILE = (
    f"{US_CORE_PROFILE_BASE}/us-core-laboratory-result-observation|6.1.0"
)

SUPPORTED_CATEGORIES = ("vital-signs", "laboratory")

# Match US Core's "blood pressure panel" LOINC so the BP profile is auto-chosen.
BLOOD_PRESSURE_PANEL_LOINC = "85354-9"

# Namespace for deterministic Observation UUID5s (same namespace as the Bundle
# fullUrl namespace in fhir/bundle.py).
_URL_NAMESPACE = uuid.UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8")


@dataclass(frozen=True, slots=True)
class Quantity:
    """A measured numeric value with a UCUM unit."""

    value: float
    unit: str                 # Human-readable unit, e.g. "mg/dL"
    code: str | None = None   # UCUM code; defaults to `unit` when omitted
    system: str = UCUM_SYSTEM


@dataclass(frozen=True, slots=True)
class ObservationComponent:
    """One named component of a multi-valued Observation (e.g., SBP within BP)."""

    code: Coding
    value: Quantity


def observation_id(gpx: GPX, observation_spec_id: str) -> str:
    """Deterministic Observation.id derived from GPX + spec id."""
    return str(uuid.uuid5(_URL_NAMESPACE, f"{gpx}:observation:{observation_spec_id}"))


def _category_element(category: str) -> dict[str, Any]:
    display = "Vital Signs" if category == "vital-signs" else "Laboratory"
    return {
        "coding": [
            {
                "system": OBSERVATION_CATEGORY_SYSTEM,
                "code": category,
                "display": display,
            }
        ]
    }




def _quantity_element(q: Quantity) -> dict[str, Any]:
    return {
        "value": q.value,
        "unit": q.unit,
        "system": q.system,
        "code": q.code or q.unit,
    }


def _default_profile(category: str, code: Coding) -> str:
    if category == "laboratory":
        return US_CORE_LAB_RESULT_PROFILE
    # vital-signs
    if code.code == BLOOD_PRESSURE_PANEL_LOINC:
        return US_CORE_BLOOD_PRESSURE_PROFILE
    return US_CORE_VITAL_SIGNS_PROFILE


def build_observation_resource(
    gpx: GPX,
    patient_fullurl: str,
    observation_spec_id: str,
    *,
    category: str,
    code: Coding,
    effective: date | datetime,
    value: Quantity | None = None,
    components: tuple[ObservationComponent, ...] = (),
    status: str = "final",
    profile_url: str | None = None,
) -> dict[str, Any]:
    """Build a US Core-conformant Observation resource."""
    if category not in SUPPORTED_CATEGORIES:
        raise ValueError(
            f"unsupported category {category!r}; choices: {list(SUPPORTED_CATEGORIES)}"
        )
    if value is None and not components:
        raise ValueError("build_observation_resource needs either `value` or `components`")
    if value is not None and components:
        raise ValueError(
            "build_observation_resource: pass `value` XOR `components`, not both"
        )

    profile = profile_url or _default_profile(category, code)

    resource: dict[str, Any] = {
        "resourceType": "Observation",
        "id": observation_id(gpx, observation_spec_id),
        "meta": {
            "profile": [profile],
            "tag": [GPX.synthetic_meta_tag()],
        },
        "status": status,
        "category": [_category_element(category)],
        "code": {
            "coding": [
                {
                    "system": code.system,
                    "code": code.code,
                    "display": code.display,
                }
            ],
            "text": code.display,
        },
        "subject": {"reference": patient_fullurl},
        "effectiveDateTime": fhir_datetime(effective),
    }

    if value is not None:
        resource["valueQuantity"] = _quantity_element(value)
    else:
        resource["component"] = [
            {
                "code": {
                    "coding": [
                        {
                            "system": comp.code.system,
                            "code": comp.code.code,
                            "display": comp.code.display,
                        }
                    ],
                    "text": comp.code.display,
                },
                "valueQuantity": _quantity_element(comp.value),
            }
            for comp in components
        ]

    _Observation.model_validate(resource)
    return resource

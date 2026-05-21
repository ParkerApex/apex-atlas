"""
FHIR R4 mortality support resources.

Atlas records death in three places when a module mortality hook fires:
Patient.deceasedDateTime, a terminal Condition, and an Observation carrying
the coded cause of death.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from fhir.resources.R4B.observation import Observation as _Observation

from parker_atlas.fhir._datetime import fhir_datetime
from parker_atlas.gpx import GPX
from parker_atlas.modules.runtime import Coding

CAUSE_OF_DEATH_LOINC = Coding(
    system="http://loinc.org",
    code="69453-9",
    display="Cause of death [US Standard Certificate of Death]",
)
OBSERVATION_CATEGORY_SYSTEM = (
    "http://terminology.hl7.org/CodeSystem/observation-category"
)

_URL_NAMESPACE = uuid.UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8")


def cause_of_death_observation_id(gpx: GPX, condition_spec_id: str) -> str:
    """Deterministic cause-of-death Observation.id."""
    return str(uuid.uuid5(_URL_NAMESPACE, f"{gpx}:cause-of-death:{condition_spec_id}"))


def build_cause_of_death_observation_resource(
    gpx: GPX,
    patient_fullurl: str,
    condition_spec_id: str,
    *,
    cause_code: Coding,
    effective: date | datetime,
) -> dict[str, Any]:
    """Build an Observation with a coded cause of death."""
    resource: dict[str, Any] = {
        "resourceType": "Observation",
        "id": cause_of_death_observation_id(gpx, condition_spec_id),
        "meta": {"tag": [GPX.synthetic_meta_tag()]},
        "status": "final",
        "category": [
            {
                "coding": [
                    {
                        "system": OBSERVATION_CATEGORY_SYSTEM,
                        "code": "exam",
                        "display": "Exam",
                    }
                ]
            }
        ],
        "code": {
            "coding": [
                {
                    "system": CAUSE_OF_DEATH_LOINC.system,
                    "code": CAUSE_OF_DEATH_LOINC.code,
                    "display": CAUSE_OF_DEATH_LOINC.display,
                }
            ],
            "text": CAUSE_OF_DEATH_LOINC.display,
        },
        "subject": {"reference": patient_fullurl},
        "effectiveDateTime": fhir_datetime(effective),
        "valueCodeableConcept": {
            "coding": [
                {
                    "system": cause_code.system,
                    "code": cause_code.code,
                    "display": cause_code.display,
                }
            ],
            "text": cause_code.display,
        },
    }
    _Observation.model_validate(resource)
    return resource

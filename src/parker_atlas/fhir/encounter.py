"""
FHIR R4 Encounter resource construction.

Produces a US Core 6.1-conformant Encounter attached to a Patient by
fullUrl. Supported classes today are the most common outpatient and
inpatient kinds (AMB, IMP, EMER, HH, VR) from v3-ActCode. Encounter
type is an open vocabulary; callers typically pass a SNOMED coding
(e.g., 185349003 "Encounter for check up").

Required elements the builder always populates:
- identifier (deterministic from GPX + spec id, US Core requires ≥1)
- status, class, type, subject, period
- meta.tag with the HL7 HTEST marker
- meta.profile claiming us-core-encounter|6.1.0
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from fhir.resources.R4B.encounter import Encounter as _Encounter

from parker_atlas.fhir._datetime import fhir_datetime
from parker_atlas.gpx import GPX
from parker_atlas.modules.runtime import Coding

V3_ACT_CODE_SYSTEM = "http://terminology.hl7.org/CodeSystem/v3-ActCode"
US_CORE_ENCOUNTER_PROFILE = (
    "http://hl7.org/fhir/us/core/StructureDefinition/us-core-encounter|6.1.0"
)
PARKER_ENCOUNTER_IDENTIFIER_SYSTEM = "https://parkerapex.com/atlas/encounter"

# Supported v3-ActCode encounter classes with their display strings.
ENCOUNTER_CLASSES: dict[str, str] = {
    "AMB": "ambulatory",
    "IMP": "inpatient encounter",
    "EMER": "emergency",
    "HH": "home health",
    "VR": "virtual",
}

_URL_NAMESPACE = uuid.UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8")


def encounter_id(gpx: GPX, encounter_spec_id: str) -> str:
    """Deterministic Encounter.id derived from GPX + spec id."""
    return str(uuid.uuid5(_URL_NAMESPACE, f"{gpx}:encounter:{encounter_spec_id}"))


def _class_element(class_code: str) -> dict[str, Any]:
    if class_code not in ENCOUNTER_CLASSES:
        raise ValueError(
            f"unsupported encounter class {class_code!r}; "
            f"choices: {sorted(ENCOUNTER_CLASSES)}"
        )
    return {
        "system": V3_ACT_CODE_SYSTEM,
        "code": class_code,
        "display": ENCOUNTER_CLASSES[class_code],
    }


def build_encounter_resource(
    gpx: GPX,
    patient_fullurl: str,
    encounter_spec_id: str,
    *,
    class_code: str,
    type_code: Coding,
    period_start: date | datetime,
    period_end: date | datetime | None = None,
    status: str = "finished",
    reason_code: Coding | None = None,
    practitioner_fullurl: str | None = None,
    location_fullurl: str | None = None,
    service_provider_fullurl: str | None = None,
) -> dict[str, Any]:
    """Build a US Core Encounter resource for a patient visit."""
    identifier_value = encounter_id(gpx, encounter_spec_id)
    resource: dict[str, Any] = {
        "resourceType": "Encounter",
        "id": identifier_value,
        "meta": {
            "profile": [US_CORE_ENCOUNTER_PROFILE],
            "tag": [GPX.synthetic_meta_tag()],
        },
        "identifier": [
            {
                "system": PARKER_ENCOUNTER_IDENTIFIER_SYSTEM,
                "value": identifier_value,
            }
        ],
        "status": status,
        "class": _class_element(class_code),
        "type": [
            {
                "coding": [
                    {
                        "system": type_code.system,
                        "code": type_code.code,
                        "display": type_code.display,
                    }
                ],
                "text": type_code.display,
            }
        ],
        "subject": {"reference": patient_fullurl},
        "period": {"start": fhir_datetime(period_start)},
    }

    if period_end is not None:
        resource["period"]["end"] = fhir_datetime(period_end)

    if practitioner_fullurl is not None:
        resource["participant"] = [
            {
                "type": [
                    {
                        "coding": [
                            {
                                "system": (
                                    "http://terminology.hl7.org/CodeSystem/"
                                    "v3-ParticipationType"
                                ),
                                "code": "ATND",
                                "display": "attender",
                            }
                        ]
                    }
                ],
                "individual": {"reference": practitioner_fullurl},
            }
        ]

    if location_fullurl is not None:
        resource["location"] = [
            {
                "location": {"reference": location_fullurl},
                "status": "completed",
            }
        ]

    if service_provider_fullurl is not None:
        resource["serviceProvider"] = {"reference": service_provider_fullurl}

    if reason_code is not None:
        resource["reasonCode"] = [
            {
                "coding": [
                    {
                        "system": reason_code.system,
                        "code": reason_code.code,
                        "display": reason_code.display,
                    }
                ],
                "text": reason_code.display,
            }
        ]

    _Encounter.model_validate(resource)
    return resource

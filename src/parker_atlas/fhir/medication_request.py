"""
FHIR R4 MedicationRequest resource construction.

Produces a US Core 6.1-conformant MedicationRequest attached to a
Patient by fullUrl, using an inline `medicationCodeableConcept`
(typically an RxNorm coding) rather than a separate Medication
resource reference.

Required elements the builder always populates:
- status, intent, medication[x], subject, authoredOn
- meta.tag with the HL7 HTEST marker
- meta.profile claiming us-core-medicationrequest|6.1.0

Optional:
- reason_code for the "why" (often a SNOMED coding for the
  associated Condition)
- encounter reference to link the prescription to a visit
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from fhir.resources.R4B.medicationrequest import MedicationRequest as _MedicationRequest

from parker_atlas.fhir._datetime import fhir_datetime
from parker_atlas.gpx import GPX
from parker_atlas.modules.runtime import Coding

US_CORE_MEDICATION_REQUEST_PROFILE = (
    "http://hl7.org/fhir/us/core/StructureDefinition/us-core-medicationrequest|6.1.0"
)

ALLOWED_STATUSES = (
    "active",
    "on-hold",
    "cancelled",
    "completed",
    "entered-in-error",
    "stopped",
    "draft",
    "unknown",
)
ALLOWED_INTENTS = (
    "proposal",
    "plan",
    "order",
    "original-order",
    "reflex-order",
    "filler-order",
    "instance-order",
    "option",
)

_URL_NAMESPACE = uuid.UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8")


def medication_request_id(gpx: GPX, spec_id: str) -> str:
    """Deterministic MedicationRequest.id derived from GPX + spec id."""
    return str(uuid.uuid5(_URL_NAMESPACE, f"{gpx}:medicationrequest:{spec_id}"))


def build_medication_request_resource(
    gpx: GPX,
    patient_fullurl: str,
    medication_spec_id: str,
    *,
    medication_code: Coding,
    authored_on: date | datetime,
    status: str = "active",
    intent: str = "order",
    reason_code: Coding | None = None,
    encounter_fullurl: str | None = None,
) -> dict[str, Any]:
    """Build a US Core MedicationRequest for a patient."""
    if status not in ALLOWED_STATUSES:
        raise ValueError(
            f"unsupported status {status!r}; choices: {list(ALLOWED_STATUSES)}"
        )
    if intent not in ALLOWED_INTENTS:
        raise ValueError(
            f"unsupported intent {intent!r}; choices: {list(ALLOWED_INTENTS)}"
        )

    resource: dict[str, Any] = {
        "resourceType": "MedicationRequest",
        "id": medication_request_id(gpx, medication_spec_id),
        "meta": {
            "profile": [US_CORE_MEDICATION_REQUEST_PROFILE],
            "tag": [GPX.synthetic_meta_tag()],
        },
        "status": status,
        "intent": intent,
        "medicationCodeableConcept": {
            "coding": [
                {
                    "system": medication_code.system,
                    "code": medication_code.code,
                    "display": medication_code.display,
                }
            ],
            "text": medication_code.display,
        },
        "subject": {"reference": patient_fullurl},
        "authoredOn": fhir_datetime(authored_on),
    }

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

    if encounter_fullurl is not None:
        resource["encounter"] = {"reference": encounter_fullurl}

    _MedicationRequest.model_validate(resource)
    return resource

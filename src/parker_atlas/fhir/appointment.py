"""
FHIR R4 Appointment resource construction.

An Appointment books a patient into a previously-published Slot. This is not
part of the SMART Scheduling Links publish payload itself (which advertises
open availability), but it is emitted alongside a published dataset so a
downstream system has a realistic set of booked encounters to reconcile
against the Slot stream.

Appointments are keyed deterministically by (slot id, patient id).
"""

from __future__ import annotations

import uuid
from typing import Any

from fhir.resources.R4B.appointment import Appointment as _Appointment

from parker_atlas.gpx import GPX
from parker_atlas.modules.runtime import Coding

PARKER_APPOINTMENT_IDENTIFIER_SYSTEM = "https://parkerapex.com/atlas/appointment"

_URL_NAMESPACE = uuid.UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8")


def appointment_id(*, slot_id: str, patient_id: str) -> str:
    """Deterministic Appointment.id keyed by slot + patient."""
    return str(uuid.uuid5(_URL_NAMESPACE, f"appointment:{slot_id}:{patient_id}"))


def build_appointment_resource(
    *,
    patient_id: str,
    slot_id: str,
    location_id: str,
    service_type: Coding,
    start: str,
    end: str,
    minutes_duration: int,
    created: str,
    location_display: str | None = None,
    service_category_code: str | None = None,
    service_category_display: str | None = None,
    status: str = "booked",
) -> dict[str, Any]:
    """Build a FHIR Appointment booking a patient into a Slot.

    Patient and Location are referenced by relative reference
    (`Patient/<id>`, `Location/<id>`); `slot` references the published Slot.
    """
    rid = appointment_id(slot_id=slot_id, patient_id=patient_id)
    patient_actor: dict[str, Any] = {"reference": f"Patient/{patient_id}"}
    location_actor: dict[str, Any] = {"reference": f"Location/{location_id}"}
    if location_display is not None:
        location_actor["display"] = location_display

    resource: dict[str, Any] = {
        "resourceType": "Appointment",
        "id": rid,
        "meta": {"tag": [GPX.synthetic_meta_tag()]},
        "identifier": [{"system": PARKER_APPOINTMENT_IDENTIFIER_SYSTEM, "value": rid}],
        "status": status,
        "serviceType": [
            {
                "coding": [
                    {
                        "system": service_type.system,
                        "code": service_type.code,
                        "display": service_type.display,
                    }
                ],
                "text": service_type.display,
            }
        ],
        "minutesDuration": minutes_duration,
        "start": start,
        "end": end,
        "created": created,
        "slot": [{"reference": f"Slot/{slot_id}"}],
        "participant": [
            {"actor": patient_actor, "status": "accepted", "required": "required"},
            {"actor": location_actor, "status": "accepted", "required": "required"},
        ],
    }
    if service_category_code is not None:
        resource["serviceCategory"] = [
            {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/service-category",
                        "code": service_category_code,
                        "display": service_category_display,
                    }
                ]
            }
        ]

    _Appointment.model_validate(resource)
    return resource

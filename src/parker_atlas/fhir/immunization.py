"""
FHIR R4 Immunization resource construction (US Core 6.1).

Immunizations are emitted as completed vaccine administrations with a
CVX-coded vaccine and occurrence date.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from fhir.resources.R4B.immunization import Immunization as _Immunization

from parker_atlas.fhir._datetime import fhir_datetime
from parker_atlas.gpx import GPX
from parker_atlas.modules.runtime import Coding

US_CORE_IMMUNIZATION_PROFILE = (
    "http://hl7.org/fhir/us/core/StructureDefinition/us-core-immunization|6.1.0"
)
PARKER_IMMUNIZATION_IDENTIFIER_SYSTEM = "https://parkerapex.com/atlas/immunization"

_URL_NAMESPACE = uuid.UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8")


def immunization_id(gpx: GPX, immunization_spec_id: str) -> str:
    """Deterministic Immunization.id derived from GPX + spec id."""
    return str(uuid.uuid5(_URL_NAMESPACE, f"{gpx}:immunization:{immunization_spec_id}"))


def build_immunization_resource(
    gpx: GPX,
    patient_fullurl: str,
    immunization_spec_id: str,
    *,
    vaccine_code: Coding,
    occurrence: date | datetime,
    status: str = "completed",
    encounter_fullurl: str | None = None,
) -> dict[str, Any]:
    """Build a US Core Immunization resource."""
    rid = immunization_id(gpx, immunization_spec_id)
    resource: dict[str, Any] = {
        "resourceType": "Immunization",
        "id": rid,
        "meta": {
            "profile": [US_CORE_IMMUNIZATION_PROFILE],
            "tag": [GPX.synthetic_meta_tag()],
        },
        "identifier": [
            {
                "system": PARKER_IMMUNIZATION_IDENTIFIER_SYSTEM,
                "value": rid,
            }
        ],
        "status": status,
        "vaccineCode": {
            "coding": [
                {
                    "system": vaccine_code.system,
                    "code": vaccine_code.code,
                    "display": vaccine_code.display,
                }
            ],
            "text": vaccine_code.display,
        },
        "patient": {"reference": patient_fullurl},
        "occurrenceDateTime": fhir_datetime(occurrence),
        "primarySource": False,
    }
    if encounter_fullurl is not None:
        resource["encounter"] = {"reference": encounter_fullurl}

    _Immunization.model_validate(resource)
    return resource

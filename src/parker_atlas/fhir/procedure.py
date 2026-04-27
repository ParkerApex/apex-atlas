"""
FHIR R4 Procedure resource construction.

Produces a US Core 6.1-conformant Procedure attached to a Patient by
fullUrl. Procedures represent completed clinical actions (surgeries,
imaging studies, catheterizations, scopes, etc.) — distinct from
Encounters (visits) and Observations (measurements).

The builder treats every Atlas-emitted Procedure as `status: completed`
since the snapshot model only reflects events that have already
happened. In-progress / scheduled / preparation states would require
the temporal-event model that lives behind Atlas's longitudinal
roadmap (see issue #3 deliverables).

Required elements the builder always populates:
- identifier (deterministic from GPX + spec id; US Core must-support)
- status, code, subject
- performedDateTime
- meta.tag with the HL7 HTEST marker
- meta.profile claiming us-core-procedure|6.1.0
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from fhir.resources.R4B.procedure import Procedure as _Procedure

from parker_atlas.fhir._datetime import fhir_datetime
from parker_atlas.gpx import GPX
from parker_atlas.modules.runtime import Coding

US_CORE_PROCEDURE_PROFILE = (
    "http://hl7.org/fhir/us/core/StructureDefinition/us-core-procedure|6.1.0"
)
PARKER_PROCEDURE_IDENTIFIER_SYSTEM = "https://parkerapex.com/atlas/procedure"

_URL_NAMESPACE = uuid.UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8")


def procedure_id(gpx: GPX, procedure_spec_id: str) -> str:
    """Deterministic Procedure.id derived from GPX + spec id."""
    return str(uuid.uuid5(_URL_NAMESPACE, f"{gpx}:procedure:{procedure_spec_id}"))


def build_procedure_resource(
    gpx: GPX,
    patient_fullurl: str,
    procedure_spec_id: str,
    *,
    code: Coding,
    performed_date: date | datetime,
    status: str = "completed",
    reason_code: Coding | None = None,
    encounter_fullurl: str | None = None,
) -> dict[str, Any]:
    """Build a US Core Procedure resource for a clinical action.

    `code` is the procedure itself (e.g., SNOMED 40701008 for
    echocardiography). `reason_code`, when provided, populates
    `reasonCode` — the clinical indication (e.g., heart failure).
    `encounter_fullurl`, when provided, populates `encounter` so the
    procedure links back to the visit at which it was performed.
    """
    identifier_value = procedure_id(gpx, procedure_spec_id)
    resource: dict[str, Any] = {
        "resourceType": "Procedure",
        "id": identifier_value,
        "meta": {
            "profile": [US_CORE_PROCEDURE_PROFILE],
            "tag": [GPX.synthetic_meta_tag()],
        },
        "identifier": [
            {
                "system": PARKER_PROCEDURE_IDENTIFIER_SYSTEM,
                "value": identifier_value,
            }
        ],
        "status": status,
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
        "performedDateTime": fhir_datetime(performed_date),
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

    _Procedure.model_validate(resource)
    return resource

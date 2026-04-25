"""
FHIR R4 Condition resource construction for problem-list entries.

Produces a US Core 6.1-conformant Condition on the "Problems and Health
Concerns" profile, referencing a Patient by fullUrl.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from fhir.resources.R4B.condition import Condition as _Condition

from parker_atlas.fhir._datetime import fhir_datetime
from parker_atlas.gpx import GPX
from parker_atlas.modules.runtime import Coding

US_CORE_CONDITION_PL_PROFILE = (
    "http://hl7.org/fhir/us/core/StructureDefinition/"
    "us-core-condition-problems-health-concerns|6.1.0"
)

CLINICAL_STATUS_SYSTEM = "http://terminology.hl7.org/CodeSystem/condition-clinical"
VERIFICATION_STATUS_SYSTEM = "http://terminology.hl7.org/CodeSystem/condition-ver-status"
CATEGORY_SYSTEM = "http://terminology.hl7.org/CodeSystem/condition-category"

# Same namespace used for Bundle fullUrls, so Condition ids are stable across
# runs with the same seed.
_URL_NAMESPACE = uuid.UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8")


def condition_id(gpx: GPX, condition_spec_id: str) -> str:
    """Deterministic Condition.id derived from patient GPX + condition spec id."""
    return str(uuid.uuid5(_URL_NAMESPACE, f"{gpx}:condition:{condition_spec_id}"))


def build_condition_resource(
    gpx: GPX,
    patient_fullurl: str,
    condition_spec_id: str,
    code: Coding,
    *,
    onset_date: date | datetime | None = None,
) -> dict[str, Any]:
    """Build a US Core Problem-List-Item Condition referencing the patient.

    `onset_date`, when provided, populates Condition.onsetDateTime — the
    moment the condition is recorded as having begun. Used by modules that
    declare an `onset_age` range to give synthetic patients a realistic
    diagnosis history rather than every condition starting "today".
    """
    resource: dict[str, Any] = {
        "resourceType": "Condition",
        "id": condition_id(gpx, condition_spec_id),
        "meta": {
            "profile": [US_CORE_CONDITION_PL_PROFILE],
            "tag": [GPX.synthetic_meta_tag()],
        },
        "clinicalStatus": {
            "coding": [
                {
                    "system": CLINICAL_STATUS_SYSTEM,
                    "code": "active",
                    "display": "Active",
                }
            ]
        },
        "verificationStatus": {
            "coding": [
                {
                    "system": VERIFICATION_STATUS_SYSTEM,
                    "code": "confirmed",
                    "display": "Confirmed",
                }
            ]
        },
        "category": [
            {
                "coding": [
                    {
                        "system": CATEGORY_SYSTEM,
                        "code": "problem-list-item",
                        "display": "Problem List Item",
                    }
                ]
            }
        ],
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
    }
    if onset_date is not None:
        resource["onsetDateTime"] = fhir_datetime(onset_date)
    _Condition.model_validate(resource)
    return resource

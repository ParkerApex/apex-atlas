"""
FHIR R4 AllergyIntolerance resource construction (US Core 6.1).

Atlas emits allergies as asserted, active clinical facts tied to the
Patient. The builder supports the common minimal case: a coded allergen,
optional reaction manifestation, and recorded date.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from fhir.resources.R4B.allergyintolerance import AllergyIntolerance as _Allergy

from parker_atlas.fhir._datetime import fhir_datetime
from parker_atlas.gpx import GPX
from parker_atlas.modules.runtime import Coding

US_CORE_ALLERGY_INTOLERANCE_PROFILE = (
    "http://hl7.org/fhir/us/core/StructureDefinition/us-core-allergyintolerance|6.1.0"
)
CLINICAL_STATUS_SYSTEM = "http://terminology.hl7.org/CodeSystem/allergyintolerance-clinical"
VERIFICATION_STATUS_SYSTEM = (
    "http://terminology.hl7.org/CodeSystem/allergyintolerance-verification"
)

_URL_NAMESPACE = uuid.UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8")


def allergy_intolerance_id(gpx: GPX, allergy_spec_id: str) -> str:
    """Deterministic AllergyIntolerance.id derived from GPX + spec id."""
    return str(uuid.uuid5(_URL_NAMESPACE, f"{gpx}:allergy:{allergy_spec_id}"))


def _codeable(code: Coding) -> dict[str, Any]:
    return {
        "coding": [
            {
                "system": code.system,
                "code": code.code,
                "display": code.display,
            }
        ],
        "text": code.display,
    }


def build_allergy_intolerance_resource(
    gpx: GPX,
    patient_fullurl: str,
    allergy_spec_id: str,
    *,
    code: Coding,
    recorded_date: date | datetime,
    category: str = "medication",
    criticality: str = "low",
    reaction_manifestation: Coding | None = None,
) -> dict[str, Any]:
    """Build a US Core AllergyIntolerance resource."""
    resource: dict[str, Any] = {
        "resourceType": "AllergyIntolerance",
        "id": allergy_intolerance_id(gpx, allergy_spec_id),
        "meta": {
            "profile": [US_CORE_ALLERGY_INTOLERANCE_PROFILE],
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
        "type": "allergy",
        "category": [category],
        "criticality": criticality,
        "code": _codeable(code),
        "patient": {"reference": patient_fullurl},
        "recordedDate": fhir_datetime(recorded_date),
    }

    if reaction_manifestation is not None:
        resource["reaction"] = [
            {"manifestation": [_codeable(reaction_manifestation)]}
        ]

    _Allergy.model_validate(resource)
    return resource

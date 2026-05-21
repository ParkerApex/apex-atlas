"""
FHIR R4 Coverage resource construction (US Core 6.1).

A Coverage links a Patient (beneficiary) to a payer Organization and
optionally an InsurancePlan, declaring the regulatory category
(Medicare, Medicaid, commercial). One Coverage per patient is the
common case; multi-payer (primary + secondary) is supported by passing
a non-default ``order``.

US Core 6.1 us-core-coverage profile must-support elements satisfied:
- identifier (Parker subscriber id)
- status
- type (coding from SOP — Source of Payment Typology)
- subscriber (the patient, for synthetic data)
- subscriberId
- beneficiary
- relationship (defaulted to "self")
- payor (the payer Organization)
- class (optional; populated with the payer's group when InsurancePlan present)
"""

from __future__ import annotations

import uuid
from typing import Any

from fhir.resources.R4B.coverage import Coverage as _Coverage

from parker_atlas.gpx import GPX

US_CORE_COVERAGE_PROFILE = (
    "http://hl7.org/fhir/us/core/StructureDefinition/us-core-coverage|6.1.0"
)

# Source of Payment Typology (NAHDO SOPT) — required by US Core Coverage.type.
SOPT_SYSTEM = "https://nahdo.org/sopt"
SUBSCRIBER_RELATIONSHIP_SYSTEM = (
    "http://terminology.hl7.org/CodeSystem/subscriber-relationship"
)
COVERAGE_CLASS_SYSTEM = (
    "http://terminology.hl7.org/CodeSystem/coverage-class"
)
PARKER_COVERAGE_IDENTIFIER_SYSTEM = "https://parkerapex.com/atlas/coverage"
PARKER_SUBSCRIBER_ID_SYSTEM = "https://parkerapex.com/atlas/subscriber"

# payer_type → (SOPT code, display).  Codes from the public SOPT v9.2.
PAYER_TYPE_TO_SOPT: dict[str, tuple[str, str]] = {
    "medicare":           ("11", "Medicare (Managed Care)"),
    "medicare-advantage": ("111", "Medicare Advantage"),
    "medicaid":           ("2",  "Medicaid"),
    "commercial":         ("5",  "Private Health Insurance"),
}

_URL_NAMESPACE = uuid.UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8")


def coverage_id(gpx: GPX, payer_id: str) -> str:
    """Deterministic Coverage.id derived from patient GPX + payer id."""
    return str(uuid.uuid5(_URL_NAMESPACE, f"{gpx}:coverage:{payer_id}"))


def subscriber_id(gpx: GPX, payer_id: str) -> str:
    """Deterministic synthetic subscriber id (per-patient, per-payer).

    Resolves the certification need for "contract member identifiers for
    matching": every synthetic patient has a stable, payer-scoped member id
    derived from GPX, so external matching tests can deterministically link
    Coverage → claims → patient.
    """
    return f"SYN-{uuid.uuid5(_URL_NAMESPACE, f'{gpx}:sub:{payer_id}').hex[:10].upper()}"


def build_coverage_resource(
    *,
    gpx: GPX,
    patient_fullurl: str,
    payer_id: str,
    payer_type: str,
    payer_organization_fullurl: str,
    insurance_plan_fullurl: str | None = None,
    order: int = 1,
    status: str = "active",
) -> dict[str, Any]:
    """Build a US Core Coverage linking the patient to a payer."""
    sopt_code, sopt_display = PAYER_TYPE_TO_SOPT.get(
        payer_type, ("9", "No Typology Code Available")
    )
    sub_id = subscriber_id(gpx, payer_id)

    resource: dict[str, Any] = {
        "resourceType": "Coverage",
        "id": coverage_id(gpx, payer_id),
        "meta": {
            "profile": [US_CORE_COVERAGE_PROFILE],
            "tag": [GPX.synthetic_meta_tag()],
        },
        "identifier": [
            {
                "system": PARKER_COVERAGE_IDENTIFIER_SYSTEM,
                "value": coverage_id(gpx, payer_id),
            }
        ],
        "status": status,
        "type": {
            "coding": [
                {
                    "system": SOPT_SYSTEM,
                    "code": sopt_code,
                    "display": sopt_display,
                }
            ],
            "text": sopt_display,
        },
        "subscriber": {"reference": patient_fullurl},
        "subscriberId": sub_id,
        "beneficiary": {"reference": patient_fullurl},
        "relationship": {
            "coding": [
                {
                    "system": SUBSCRIBER_RELATIONSHIP_SYSTEM,
                    "code": "self",
                    "display": "Self",
                }
            ]
        },
        "payor": [{"reference": payer_organization_fullurl}],
        "order": order,
    }

    if insurance_plan_fullurl is not None:
        resource["class"] = [
            {
                "type": {
                    "coding": [
                        {
                            "system": COVERAGE_CLASS_SYSTEM,
                            "code": "plan",
                            "display": "Plan",
                        }
                    ]
                },
                "value": payer_id,
                "name": payer_id,
            }
        ]

    _Coverage.model_validate(resource)
    return resource

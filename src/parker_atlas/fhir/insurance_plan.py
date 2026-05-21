"""
FHIR R4 InsurancePlan resource construction.

Base R4 InsurancePlan (US Core 6.1 does not currently profile InsurancePlan;
Da Vinci PDex Plan-Net does, and is the future target). One InsurancePlan per
payer is sufficient for placeholder coverage modelling; per-product plans (HMO
vs. PPO vs. EPO, etc.) will land alongside fee schedules in item #3.
"""

from __future__ import annotations

import uuid
from typing import Any

from fhir.resources.R4B.insuranceplan import InsurancePlan as _InsurancePlan

from parker_atlas.gpx import GPX
from parker_atlas.fhir.organization import payer_organization_id

PLAN_TYPE_SYSTEM = "http://terminology.hl7.org/CodeSystem/insurance-plan-type"
PARKER_PLAN_IDENTIFIER_SYSTEM = "https://parkerapex.com/atlas/insurance-plan"

_URL_NAMESPACE = uuid.UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8")


# Map payer_type → InsurancePlan.type code. The HL7 insurance-plan-type
# value set is open; values below are illustrative defaults.
PAYER_TYPE_TO_PLAN_TYPE: dict[str, tuple[str, str]] = {
    "medicare":           ("medical", "Medical"),
    "medicare-advantage": ("medical", "Medical"),
    "medicaid":           ("medical", "Medical"),
    "commercial":         ("medical", "Medical"),
}


def insurance_plan_id(payer_id: str) -> str:
    """Deterministic InsurancePlan.id derived from the payer id."""
    return str(uuid.uuid5(_URL_NAMESPACE, f"insurance-plan:{payer_id}"))


def build_insurance_plan_resource(
    *,
    payer_id: str,
    payer_type: str,
    plan_name: str,
    payer_organization_fullurl: str,
) -> dict[str, Any]:
    """Build a base R4 InsurancePlan owned by the payer organization."""
    plan_code, plan_display = PAYER_TYPE_TO_PLAN_TYPE.get(
        payer_type, ("medical", "Medical")
    )
    resource: dict[str, Any] = {
        "resourceType": "InsurancePlan",
        "id": insurance_plan_id(payer_id),
        "meta": {"tag": [GPX.synthetic_meta_tag()]},
        "identifier": [
            {
                "system": PARKER_PLAN_IDENTIFIER_SYSTEM,
                "value": payer_id,
            }
        ],
        "status": "active",
        "type": [
            {
                "coding": [
                    {
                        "system": PLAN_TYPE_SYSTEM,
                        "code": plan_code,
                        "display": plan_display,
                    }
                ]
            }
        ],
        "name": plan_name,
        "ownedBy": {"reference": payer_organization_fullurl},
    }
    _InsurancePlan.model_validate(resource)
    # Silence unused-import lints if payer_organization_id is removed later.
    assert payer_organization_id is not None
    return resource

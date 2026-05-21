"""
FHIR R4 Claim and ExplanationOfBenefit construction.

This is Atlas's first synthetic revenue-cycle slice: one professional
Claim per Encounter, plus a paired ExplanationOfBenefit showing simple
adjudication. Amounts are deterministic from Encounter class and payer
category so seeded runs remain byte-stable.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from fhir.resources.R4B.claim import Claim as _Claim
from fhir.resources.R4B.explanationofbenefit import (
    ExplanationOfBenefit as _ExplanationOfBenefit,
)

from parker_atlas.fhir._datetime import fhir_datetime
from parker_atlas.gpx import GPX
from parker_atlas.modules.runtime import Coding

PARKER_CLAIM_IDENTIFIER_SYSTEM = "https://parkerapex.com/atlas/claim"
PARKER_EOB_IDENTIFIER_SYSTEM = "https://parkerapex.com/atlas/explanation-of-benefit"
CPT_SYSTEM = "http://www.ama-assn.org/go/cpt"
USD = "USD"

_URL_NAMESPACE = uuid.UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8")


@dataclass(frozen=True, slots=True)
class ClaimCharge:
    cpt: Coding
    unit_price: Decimal


ENCOUNTER_CLASS_CHARGES: dict[str, ClaimCharge] = {
    "AMB": ClaimCharge(Coding(CPT_SYSTEM, "99213", "Office outpatient visit, established patient"), Decimal("165.00")),
    "VR": ClaimCharge(Coding(CPT_SYSTEM, "98004", "Synchronous audio-video visit"), Decimal("110.00")),
    "HH": ClaimCharge(Coding(CPT_SYSTEM, "99349", "Home visit, established patient"), Decimal("225.00")),
    "EMER": ClaimCharge(Coding(CPT_SYSTEM, "99284", "Emergency department visit"), Decimal("980.00")),
    "IMP": ClaimCharge(Coding(CPT_SYSTEM, "99222", "Initial hospital inpatient care"), Decimal("1850.00")),
}

PAYER_ALLOWED_RATIO: dict[str, Decimal] = {
    "medicare": Decimal("0.62"),
    "medicare-advantage": Decimal("0.68"),
    "medicaid": Decimal("0.48"),
    "commercial": Decimal("0.76"),
}


def _money(value: Decimal) -> dict[str, Any]:
    rounded = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return {"value": float(rounded), "currency": USD}


def claim_id(gpx: GPX, encounter_id: str) -> str:
    """Deterministic Claim.id derived from GPX + Encounter.id."""
    return str(uuid.uuid5(_URL_NAMESPACE, f"{gpx}:claim:{encounter_id}"))


def explanation_of_benefit_id(gpx: GPX, encounter_id: str) -> str:
    """Deterministic ExplanationOfBenefit.id derived from GPX + Encounter.id."""
    return str(uuid.uuid5(_URL_NAMESPACE, f"{gpx}:eob:{encounter_id}"))


def charge_for_encounter_class(class_code: str) -> ClaimCharge:
    """Return the synthetic CPT/charge mapping for an Encounter class."""
    return ENCOUNTER_CLASS_CHARGES.get(class_code, ENCOUNTER_CLASS_CHARGES["AMB"])


def _coding(code: Coding) -> dict[str, Any]:
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


def build_claim_resource(
    gpx: GPX,
    patient_fullurl: str,
    encounter_fullurl: str,
    coverage_fullurl: str,
    *,
    encounter_id_value: str,
    encounter_class: str,
    created: date | datetime,
    provider_fullurl: str | None = None,
) -> dict[str, Any]:
    """Build one professional Claim for an Encounter."""
    rid = claim_id(gpx, encounter_id_value)
    charge = charge_for_encounter_class(encounter_class)
    resource: dict[str, Any] = {
        "resourceType": "Claim",
        "id": rid,
        "meta": {"tag": [GPX.synthetic_meta_tag()]},
        "identifier": [{"system": PARKER_CLAIM_IDENTIFIER_SYSTEM, "value": rid}],
        "status": "active",
        "type": {
            "coding": [
                {
                    "system": "http://terminology.hl7.org/CodeSystem/claim-type",
                    "code": "professional",
                    "display": "Professional",
                }
            ]
        },
        "use": "claim",
        "patient": {"reference": patient_fullurl},
        "created": fhir_datetime(created),
        "provider": {"reference": provider_fullurl or patient_fullurl},
        "priority": {
            "coding": [
                {
                    "system": "http://terminology.hl7.org/CodeSystem/processpriority",
                    "code": "normal",
                    "display": "Normal",
                }
            ]
        },
        "insurance": [
            {
                "sequence": 1,
                "focal": True,
                "coverage": {"reference": coverage_fullurl},
            }
        ],
        "item": [
            {
                "sequence": 1,
                "productOrService": _coding(charge.cpt),
                "encounter": [{"reference": encounter_fullurl}],
                "unitPrice": _money(charge.unit_price),
                "net": _money(charge.unit_price),
            }
        ],
        "total": _money(charge.unit_price),
    }

    _Claim.model_validate(resource)
    return resource


def build_explanation_of_benefit_resource(
    gpx: GPX,
    patient_fullurl: str,
    encounter_fullurl: str,
    coverage_fullurl: str,
    claim_fullurl: str,
    *,
    encounter_id_value: str,
    encounter_class: str,
    payer_type: str,
    created: date | datetime,
    provider_fullurl: str | None = None,
    insurer_fullurl: str | None = None,
) -> dict[str, Any]:
    """Build a paired ExplanationOfBenefit with simple adjudication."""
    rid = explanation_of_benefit_id(gpx, encounter_id_value)
    charge = charge_for_encounter_class(encounter_class)
    allowed = charge.unit_price * PAYER_ALLOWED_RATIO.get(
        payer_type, Decimal("0.70")
    )
    patient_resp = allowed * Decimal("0.20")
    paid = allowed - patient_resp

    resource: dict[str, Any] = {
        "resourceType": "ExplanationOfBenefit",
        "id": rid,
        "meta": {"tag": [GPX.synthetic_meta_tag()]},
        "identifier": [{"system": PARKER_EOB_IDENTIFIER_SYSTEM, "value": rid}],
        "status": "active",
        "type": {
            "coding": [
                {
                    "system": "http://terminology.hl7.org/CodeSystem/claim-type",
                    "code": "professional",
                    "display": "Professional",
                }
            ]
        },
        "use": "claim",
        "patient": {"reference": patient_fullurl},
        "created": fhir_datetime(created),
        "insurer": {"reference": insurer_fullurl or coverage_fullurl},
        "provider": {"reference": provider_fullurl or patient_fullurl},
        "outcome": "complete",
        "claim": {"reference": claim_fullurl},
        "insurance": [
            {
                "focal": True,
                "coverage": {"reference": coverage_fullurl},
            }
        ],
        "item": [
            {
                "sequence": 1,
                "productOrService": _coding(charge.cpt),
                "encounter": [{"reference": encounter_fullurl}],
                "adjudication": [
                    {
                        "category": {"coding": [{"code": "submitted"}]},
                        "amount": _money(charge.unit_price),
                    },
                    {
                        "category": {"coding": [{"code": "eligible"}]},
                        "amount": _money(allowed),
                    },
                    {
                        "category": {"coding": [{"code": "benefit"}]},
                        "amount": _money(paid),
                    },
                    {
                        "category": {"coding": [{"code": "copay"}]},
                        "amount": _money(patient_resp),
                    },
                ],
            }
        ],
        "total": [
            {
                "category": {"coding": [{"code": "submitted"}]},
                "amount": _money(charge.unit_price),
            },
            {
                "category": {"coding": [{"code": "benefit"}]},
                "amount": _money(paid),
            },
        ],
    }

    _ExplanationOfBenefit.model_validate(resource)
    return resource

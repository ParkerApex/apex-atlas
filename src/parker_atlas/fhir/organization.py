"""
FHIR R4 Organization resource construction.

Two flavors are supported via the `type` argument:

- ``payer`` — a payer organization (Medicare, Medicaid, commercial plan).
  Claims US Core 6.1 us-core-organization conformance and carries a
  payer-roster identifier (Parker namespace), with a v3 OrganizationType
  coding of ``pay``.
- ``prov`` — a provider/facility organization (hospital, clinic). Same
  US Core profile, with an NPI identifier and v3 OrganizationType coding
  of ``prov``.

Both flavors emit the HL7 HTEST meta tag.
"""

from __future__ import annotations

import uuid
from typing import Any, Literal

from fhir.resources.R4B.organization import Organization as _Organization

from parker_atlas.gpx import GPX

US_CORE_ORGANIZATION_PROFILE = (
    "http://hl7.org/fhir/us/core/StructureDefinition/us-core-organization|6.1.0"
)
V3_ORG_TYPE_SYSTEM = "http://terminology.hl7.org/CodeSystem/v3-RoleCode"
PARKER_PAYER_IDENTIFIER_SYSTEM = "https://parkerapex.com/atlas/payer"
NPI_IDENTIFIER_SYSTEM = "http://hl7.org/fhir/sid/us-npi"

_URL_NAMESPACE = uuid.UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8")


def payer_organization_id(payer_id: str) -> str:
    """Deterministic Organization.id for a payer (stable across patients)."""
    return str(uuid.uuid5(_URL_NAMESPACE, f"payer:{payer_id}"))


def facility_organization_id(npi: str) -> str:
    """Deterministic Organization.id for a facility, keyed by NPI."""
    return str(uuid.uuid5(_URL_NAMESPACE, f"facility:{npi}"))


def build_payer_organization_resource(
    *,
    payer_id: str,
    name: str,
) -> dict[str, Any]:
    """Build a US Core Organization for a payer (one per payer, shared across patients)."""
    resource: dict[str, Any] = {
        "resourceType": "Organization",
        "id": payer_organization_id(payer_id),
        "meta": {
            "profile": [US_CORE_ORGANIZATION_PROFILE],
            "tag": [GPX.synthetic_meta_tag()],
        },
        "identifier": [
            {
                "system": PARKER_PAYER_IDENTIFIER_SYSTEM,
                "value": payer_id,
            }
        ],
        "active": True,
        "type": [
            {
                "coding": [
                    {
                        "system": V3_ORG_TYPE_SYSTEM,
                        "code": "pay",
                        "display": "Payer",
                    }
                ]
            }
        ],
        "name": name,
    }
    _Organization.model_validate(resource)
    return resource


def build_facility_organization_resource(
    *,
    npi: str,
    name: str,
    org_role: Literal["prov", "hosp", "clinic"] = "prov",
) -> dict[str, Any]:
    """Build a US Core Organization for a facility (hospital, clinic), keyed by NPI."""
    resource: dict[str, Any] = {
        "resourceType": "Organization",
        "id": facility_organization_id(npi),
        "meta": {
            "profile": [US_CORE_ORGANIZATION_PROFILE],
            "tag": [GPX.synthetic_meta_tag()],
        },
        "identifier": [
            {
                "system": NPI_IDENTIFIER_SYSTEM,
                "value": npi,
            }
        ],
        "active": True,
        "type": [
            {
                "coding": [
                    {
                        "system": V3_ORG_TYPE_SYSTEM,
                        "code": org_role,
                        "display": "Healthcare Provider",
                    }
                ]
            }
        ],
        "name": name,
    }
    _Organization.model_validate(resource)
    return resource

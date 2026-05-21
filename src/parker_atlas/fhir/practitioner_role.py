"""
FHIR R4 PractitionerRole resource construction (US Core 6.1).

A PractitionerRole binds a Practitioner to an Organization with a
NUCC Health Care Provider Taxonomy specialty. The id is deterministic
over (practitioner NPI, facility NPI, taxonomy code) so the same
(Dr. X at Hospital Y in Cardiology) row merges on ingest.

us-core-practitionerrole|6.1.0 requires at minimum:
- practitioner (reference to Practitioner)
- organization (reference to Organization)
- code or specialty (we populate specialty with NUCC taxonomy)
"""

from __future__ import annotations

import uuid
from typing import Any

from fhir.resources.R4B.practitionerrole import (
    PractitionerRole as _PractitionerRole,
)

from parker_atlas.gpx import GPX

US_CORE_PRACTITIONER_ROLE_PROFILE = (
    "http://hl7.org/fhir/us/core/StructureDefinition/us-core-practitionerrole|6.1.0"
)
NUCC_TAXONOMY_SYSTEM = "http://nucc.org/provider-taxonomy"

_URL_NAMESPACE = uuid.UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8")


def practitioner_role_id(
    *, practitioner_npi: str, facility_npi: str, taxonomy_code: str
) -> str:
    """Deterministic PractitionerRole.id keyed by (practitioner, facility, specialty)."""
    return str(
        uuid.uuid5(
            _URL_NAMESPACE,
            f"practitionerrole:{practitioner_npi}:{facility_npi}:{taxonomy_code}",
        )
    )


def build_practitioner_role_resource(
    *,
    practitioner_npi: str,
    facility_npi: str,
    taxonomy_code: str,
    taxonomy_display: str,
    practitioner_fullurl: str,
    facility_organization_fullurl: str,
) -> dict[str, Any]:
    """Build a US Core PractitionerRole tying a Practitioner to a facility Org."""
    resource: dict[str, Any] = {
        "resourceType": "PractitionerRole",
        "id": practitioner_role_id(
            practitioner_npi=practitioner_npi,
            facility_npi=facility_npi,
            taxonomy_code=taxonomy_code,
        ),
        "meta": {
            "profile": [US_CORE_PRACTITIONER_ROLE_PROFILE],
            "tag": [GPX.synthetic_meta_tag()],
        },
        "active": True,
        "practitioner": {"reference": practitioner_fullurl},
        "organization": {"reference": facility_organization_fullurl},
        "specialty": [
            {
                "coding": [
                    {
                        "system": NUCC_TAXONOMY_SYSTEM,
                        "code": taxonomy_code,
                        "display": taxonomy_display,
                    }
                ],
                "text": taxonomy_display,
            }
        ],
    }
    _PractitionerRole.model_validate(resource)
    return resource

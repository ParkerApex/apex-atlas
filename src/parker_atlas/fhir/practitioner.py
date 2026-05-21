"""
FHIR R4 Practitioner resource construction (US Core 6.1).

A Practitioner represents an individual clinician (NPI Type 1). The
resource is keyed deterministically off NPI so the same practitioner
emitted across multiple patients merges to one row on ingest.

us-core-practitioner|6.1.0 requires at minimum:
- identifier (NPI, system http://hl7.org/fhir/sid/us-npi)
- name (HumanName)
"""

from __future__ import annotations

import uuid
from typing import Any

from fhir.resources.R4B.practitioner import Practitioner as _Practitioner

from parker_atlas.gpx import GPX

US_CORE_PRACTITIONER_PROFILE = (
    "http://hl7.org/fhir/us/core/StructureDefinition/us-core-practitioner|6.1.0"
)
NPI_IDENTIFIER_SYSTEM = "http://hl7.org/fhir/sid/us-npi"

_URL_NAMESPACE = uuid.UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8")


def practitioner_id(npi: str) -> str:
    """Deterministic Practitioner.id keyed by NPI."""
    return str(uuid.uuid5(_URL_NAMESPACE, f"practitioner:{npi}"))


def build_practitioner_resource(
    *,
    npi: str,
    family: str,
    given: str,
    prefix: str | None = None,
) -> dict[str, Any]:
    """Build a US Core Practitioner resource (one per NPI, shared across patients)."""
    name: dict[str, Any] = {"family": family, "given": [given]}
    if prefix:
        name["prefix"] = [prefix]

    resource: dict[str, Any] = {
        "resourceType": "Practitioner",
        "id": practitioner_id(npi),
        "meta": {
            "profile": [US_CORE_PRACTITIONER_PROFILE],
            "tag": [GPX.synthetic_meta_tag()],
        },
        "identifier": [
            {"system": NPI_IDENTIFIER_SYSTEM, "value": npi},
        ],
        "active": True,
        "name": [name],
    }
    _Practitioner.model_validate(resource)
    return resource

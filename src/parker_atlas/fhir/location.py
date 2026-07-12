"""
FHIR R4 Location resource construction (US Core 6.1).

A Location is a physical place of care managed by a facility
Organization. Locations are keyed deterministically by
(facility NPI, location_name) so the same suite/department merges on
ingest across patients.

us-core-location|6.1.0 requires at minimum:
- name
- managingOrganization (we always populate from facility NPI)
- type (we populate with a v3 ServiceDeliveryLocationRoleType code)
- address (we populate from the locations.csv row)
"""

from __future__ import annotations

import uuid
from typing import Any

from fhir.resources.R4B.location import Location as _Location

from parker_atlas.gpx import GPX

US_CORE_LOCATION_PROFILE = (
    "http://hl7.org/fhir/us/core/StructureDefinition/us-core-location|6.1.0"
)
V3_LOCATION_TYPE_SYSTEM = "http://terminology.hl7.org/CodeSystem/v3-RoleCode"

_URL_NAMESPACE = uuid.UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8")


def location_id(*, facility_npi: str, location_name: str) -> str:
    """Deterministic Location.id keyed by facility + location name."""
    return str(
        uuid.uuid5(_URL_NAMESPACE, f"location:{facility_npi}:{location_name}")
    )


def build_location_resource(
    *,
    facility_npi: str,
    location_name: str,
    location_type_code: str,
    location_type_display: str,
    line: str,
    city: str,
    state: str,
    postal_code: str,
    facility_organization_fullurl: str,
) -> dict[str, Any]:
    """Build a US Core Location resource (one per facility+suite)."""
    resource: dict[str, Any] = {
        "resourceType": "Location",
        "id": location_id(facility_npi=facility_npi, location_name=location_name),
        "meta": {
            "profile": [US_CORE_LOCATION_PROFILE],
            "tag": [GPX.synthetic_meta_tag()],
        },
        "status": "active",
        "name": location_name,
        "type": [
            {
                "coding": [
                    {
                        "system": V3_LOCATION_TYPE_SYSTEM,
                        "code": location_type_code,
                        "display": location_type_display,
                    }
                ],
                "text": location_type_display,
            }
        ],
        "address": {
            "use": "work",
            "line": [line],
            "city": city,
            "state": state,
            "postalCode": postal_code,
            "country": "US",
        },
        "managingOrganization": {"reference": facility_organization_fullurl},
    }
    _Location.model_validate(resource)
    return resource


PARKER_LOCATION_IDENTIFIER_SYSTEM = "https://parkerapex.com/atlas/location"
US_NPI_SYSTEM = "http://hl7.org/fhir/sid/us-npi"


def scheduling_location_id(*, identifier_value: str) -> str:
    """Deterministic Location.id keyed by the publisher-scoped identifier."""
    return str(uuid.uuid5(_URL_NAMESPACE, f"scheduling-location:{identifier_value}"))


def build_scheduling_location_resource(
    *,
    identifier_value: str,
    name: str,
    line: str,
    city: str,
    state: str,
    postal_code: str,
    latitude: float,
    longitude: float,
    phone: str | None = None,
    url: str | None = None,
    npi: str | None = None,
    district: str | None = None,
) -> dict[str, Any]:
    """Build a standalone FHIR Location for SMART Scheduling Links publishing.

    Unlike :func:`build_location_resource` (a US Core Location managed by a
    facility Organization), a scheduling Location is self-contained: it carries
    its own identifier, contact details, address, and geographic position so a
    consumer scheduling app can render and route to the site directly.
    """
    telecom: list[dict[str, Any]] = []
    if phone is not None:
        telecom.append({"system": "phone", "value": phone, "use": "work"})
    if url is not None:
        telecom.append({"system": "url", "value": url, "use": "work"})

    identifiers: list[dict[str, Any]] = [
        {"system": PARKER_LOCATION_IDENTIFIER_SYSTEM, "value": identifier_value}
    ]
    if npi is not None:
        identifiers.append({"system": US_NPI_SYSTEM, "value": npi})

    address: dict[str, Any] = {
        "use": "work",
        "line": [line],
        "city": city,
        "state": state,
        "postalCode": postal_code,
        "country": "US",
    }
    if district is not None:
        address["district"] = district

    resource: dict[str, Any] = {
        "resourceType": "Location",
        "id": scheduling_location_id(identifier_value=identifier_value),
        "meta": {"tag": [GPX.synthetic_meta_tag()]},
        "identifier": identifiers,
        "status": "active",
        "name": name,
        "address": address,
        "position": {"latitude": latitude, "longitude": longitude},
    }
    if telecom:
        resource["telecom"] = telecom

    _Location.model_validate(resource)
    return resource

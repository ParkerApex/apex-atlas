"""
FHIR R4 Schedule resource construction for SMART Scheduling Links.

A Schedule is a container of availability (Slots) for a single service at a
single Location. In the SMART Scheduling Links `$bulk-publish` flow the
Schedule ties published Slots back to the physical site (`actor` → Location)
and names the service on offer (`serviceType`).

Schedules are keyed deterministically by (location id, service key) so the
same service at the same site merges on re-publish.
"""

from __future__ import annotations

import uuid
from typing import Any

from fhir.resources.R4B.schedule import Schedule as _Schedule

from parker_atlas.gpx import GPX
from parker_atlas.modules.runtime import Coding

SERVICE_CATEGORY_SYSTEM = "http://terminology.hl7.org/CodeSystem/service-category"
PARKER_SCHEDULE_IDENTIFIER_SYSTEM = "https://parkerapex.com/atlas/schedule"

_URL_NAMESPACE = uuid.UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8")


def schedule_id(*, location_id: str, service_key: str) -> str:
    """Deterministic Schedule.id keyed by location + service key."""
    return str(uuid.uuid5(_URL_NAMESPACE, f"schedule:{location_id}:{service_key}"))


def build_schedule_resource(
    *,
    location_id: str,
    service_key: str,
    service_type: Coding,
    service_category_code: str | None = None,
    service_category_display: str | None = None,
    horizon_start: str | None = None,
    horizon_end: str | None = None,
) -> dict[str, Any]:
    """Build a FHIR Schedule resource whose actor is a Location.

    Args:
        location_id: id of the Location this Schedule advertises availability for.
        service_key: stable slug distinguishing services at the same location.
        service_type: coded service on offer (e.g. General Practice).
        service_category_code / _display: optional HL7 service-category coding.
        horizon_start / horizon_end: ISO-8601 bounds of the planning horizon.
    """
    rid = schedule_id(location_id=location_id, service_key=service_key)
    resource: dict[str, Any] = {
        "resourceType": "Schedule",
        "id": rid,
        "meta": {"tag": [GPX.synthetic_meta_tag()]},
        "identifier": [{"system": PARKER_SCHEDULE_IDENTIFIER_SYSTEM, "value": rid}],
        "active": True,
        "serviceType": [
            {
                "coding": [
                    {
                        "system": service_type.system,
                        "code": service_type.code,
                        "display": service_type.display,
                    }
                ],
                "text": service_type.display,
            }
        ],
        "actor": [{"reference": f"Location/{location_id}"}],
    }
    if service_category_code is not None:
        resource["serviceCategory"] = [
            {
                "coding": [
                    {
                        "system": SERVICE_CATEGORY_SYSTEM,
                        "code": service_category_code,
                        "display": service_category_display,
                    }
                ]
            }
        ]
    if horizon_start is not None and horizon_end is not None:
        resource["planningHorizon"] = {"start": horizon_start, "end": horizon_end}

    _Schedule.model_validate(resource)
    return resource

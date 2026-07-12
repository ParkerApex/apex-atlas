"""
FHIR R4 Slot resource construction for SMART Scheduling Links.

A Slot is a bookable (or booked) window of time on a Schedule. The
`$bulk-publish` flow defined by SMART Scheduling Links
(https://github.com/smart-on-fhir/smart-scheduling-links) advertises open
availability as a stream of Slot resources, each carrying the SMART
booking-deep-link / booking-phone / slot-capacity extensions so a consumer
app can hand the user off to the provider's booking site.

Slots are keyed deterministically by (schedule id, start instant) so the same
window merges on re-publish.
"""

from __future__ import annotations

import uuid
from typing import Any

from fhir.resources.R4B.slot import Slot as _Slot

from parker_atlas.gpx import GPX
from parker_atlas.modules.runtime import Coding

# SMART Scheduling Links extension URLs.
SMART_EXT_BASE = "http://fhir-registry.smarthealthit.org/StructureDefinition"
BOOKING_DEEP_LINK_EXT = f"{SMART_EXT_BASE}/booking-deep-link"
BOOKING_PHONE_EXT = f"{SMART_EXT_BASE}/booking-phone"
SLOT_CAPACITY_EXT = f"{SMART_EXT_BASE}/slot-capacity"

PARKER_SLOT_IDENTIFIER_SYSTEM = "https://parkerapex.com/atlas/slot"

_URL_NAMESPACE = uuid.UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8")

_VALID_STATUS = {"free", "busy", "busy-unavailable", "busy-tentative", "entered-in-error"}


def slot_id(*, schedule_id: str, start: str) -> str:
    """Deterministic Slot.id keyed by schedule + start instant."""
    return str(uuid.uuid5(_URL_NAMESPACE, f"slot:{schedule_id}:{start}"))


def build_slot_resource(
    *,
    schedule_id: str,
    service_type: Coding,
    start: str,
    end: str,
    status: str = "free",
    booking_deep_link: str | None = None,
    booking_phone: str | None = None,
    capacity: int | None = None,
) -> dict[str, Any]:
    """Build a FHIR Slot resource with SMART Scheduling Links extensions.

    Args:
        schedule_id: id of the Schedule this Slot belongs to.
        service_type: the service offered in the Slot (mirrors the Schedule).
        start / end: ISO-8601 instants including a timezone offset.
        status: FHIR slot status (`free` or `busy` in the common case).
        booking_deep_link: URL a consumer app opens to book this slot.
        booking_phone: phone number a consumer can call to book.
        capacity: number of bookings the slot accepts (defaults omitted).
    """
    if status not in _VALID_STATUS:
        raise ValueError(f"invalid Slot.status {status!r}; expected one of {sorted(_VALID_STATUS)}")

    rid = slot_id(schedule_id=schedule_id, start=start)

    extensions: list[dict[str, Any]] = []
    if booking_deep_link is not None:
        extensions.append({"url": BOOKING_DEEP_LINK_EXT, "valueUrl": booking_deep_link})
    if booking_phone is not None:
        extensions.append({"url": BOOKING_PHONE_EXT, "valueString": booking_phone})
    if capacity is not None:
        extensions.append({"url": SLOT_CAPACITY_EXT, "valueInteger": capacity})

    resource: dict[str, Any] = {
        "resourceType": "Slot",
        "id": rid,
        "meta": {"tag": [GPX.synthetic_meta_tag()]},
        "identifier": [{"system": PARKER_SLOT_IDENTIFIER_SYSTEM, "value": rid}],
        "schedule": {"reference": f"Schedule/{schedule_id}"},
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
        "status": status,
        "start": start,
        "end": end,
    }
    if extensions:
        resource["extension"] = extensions

    _Slot.model_validate(resource)
    return resource

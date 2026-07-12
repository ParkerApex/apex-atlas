"""Build the CMS Connectathon 2026 SMART Scheduling Links bulk-publish dataset.

This script emits an appointment-availability dataset that conforms to the
SMART Scheduling Links specification
(https://github.com/smart-on-fhir/smart-scheduling-links), the "SMART FHIR
Scheduling" bulk-publish flow used to advertise open, bookable appointment
slots to consumer scheduling apps.

Outputs (written under ``samples/cms-connectathon-2026/scheduling/``):

- ``bulk-publish-manifest.json`` — the JSON document a server returns from its
  ``$bulk-publish`` operation. Its ``output`` array links the NDJSON files.
- ``Location.ndjson`` — physical clinic sites (US Core-flavored Location).
- ``Schedule.ndjson`` — one Schedule per (Location, serviceType); ``actor``
  references the Location.
- ``Slot.ndjson`` — bookable time slots (``free``/``busy``) referencing a
  Schedule, carrying the SMART Scheduling Links booking-deep-link,
  booking-phone, and slot-capacity extensions.
- ``Appointment.ndjson`` — FHIR R4 Appointments that book a subset of the
  generated patient population into ``busy`` slots (a connectathon convenience;
  not part of SMART Scheduling Links itself).

Everything is synthetic and deterministic (fixed seed + fixed dates). Patient
references are read from the companion Patient bulk export so Appointments
resolve against the same cohort.
"""

from __future__ import annotations

import json
import random
import uuid
from datetime import date, datetime, time, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SEED = 20260712
REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "samples" / "cms-connectathon-2026" / "scheduling"
PATIENT_NDJSON = (
    REPO_ROOT / "samples" / "cms-connectathon-2026" / "patients" / "Patient.ndjson"
)

# Base URL the manifest advertises for its output files. Points at the raw
# files as committed on the connectathon branch so the manifest resolves.
PUBLISH_BASE = (
    "https://raw.githubusercontent.com/ParkerApex/apex-atlas/"
    "claude/cms-connectathon-2026-dq23fb/samples/cms-connectathon-2026/scheduling"
)

# Availability window: four weeks of weekdays, 08:00–17:00 local, hourly slots.
WINDOW_START = date(2026, 7, 13)  # Monday
WINDOW_WEEKS = 4
SLOT_HOURS = list(range(8, 17))  # 08:00 .. 16:00 start times (9 slots/day)
SLOT_MINUTES = 60
TRANSACTION_TIME = "2026-07-12T00:00:00Z"

# ~20% of published slots are already booked; each booked slot gets an
# Appointment referencing a random patient from the cohort.
BOOKED_FRACTION = 0.20

SYNTHETIC_TAG = {
    "system": "http://terminology.hl7.org/CodeSystem/v3-ActReason",
    "code": "HTEST",
    "display": "test health data",
}

SMART_EXT = "http://fhir-registry.smarthealthit.org/StructureDefinition"
SERVICE_TYPE_SYSTEM = "http://terminology.hl7.org/CodeSystem/service-type"

# Two service types drawn from the FHIR service-type value set.
SERVICE_TYPES = [
    {
        "key": "gp",
        "coding": {"system": SERVICE_TYPE_SYSTEM, "code": "124", "display": "General Practice"},
        "category": {"code": "17", "display": "General Practice"},
        "minutes": 60,
    },
    {
        "key": "imm",
        "coding": {"system": SERVICE_TYPE_SYSTEM, "code": "57", "display": "Immunization"},
        "category": {"code": "31", "display": "Specialist Medical Services"},
        "minutes": 30,
    },
]

# 40 synthetic clinic sites. (city, state, tz_offset_july, lat, long)
CITIES = [
    ("Boston", "MA", "-04:00", 42.3601, -71.0589),
    ("Worcester", "MA", "-04:00", 42.2626, -71.8023),
    ("New York", "NY", "-04:00", 40.7128, -74.0060),
    ("Buffalo", "NY", "-04:00", 42.8864, -78.8784),
    ("Philadelphia", "PA", "-04:00", 39.9526, -75.1652),
    ("Pittsburgh", "PA", "-04:00", 40.4406, -79.9959),
    ("Baltimore", "MD", "-04:00", 39.2904, -76.6122),
    ("Washington", "DC", "-04:00", 38.9072, -77.0369),
    ("Richmond", "VA", "-04:00", 37.5407, -77.4360),
    ("Charlotte", "NC", "-04:00", 35.2271, -80.8431),
    ("Atlanta", "GA", "-04:00", 33.7490, -84.3880),
    ("Miami", "FL", "-04:00", 25.7617, -80.1918),
    ("Orlando", "FL", "-04:00", 28.5383, -81.3792),
    ("Tampa", "FL", "-04:00", 27.9506, -82.4572),
    ("Nashville", "TN", "-05:00", 36.1627, -86.7816),
    ("Memphis", "TN", "-05:00", 35.1495, -90.0490),
    ("Columbus", "OH", "-04:00", 39.9612, -82.9988),
    ("Cleveland", "OH", "-04:00", 41.4993, -81.6944),
    ("Detroit", "MI", "-04:00", 42.3314, -83.0458),
    ("Indianapolis", "IN", "-04:00", 39.7684, -86.1581),
    ("Chicago", "IL", "-05:00", 41.8781, -87.6298),
    ("Milwaukee", "WI", "-05:00", 43.0389, -87.9065),
    ("Minneapolis", "MN", "-05:00", 44.9778, -93.2650),
    ("St. Louis", "MO", "-05:00", 38.6270, -90.1994),
    ("Kansas City", "MO", "-05:00", 39.0997, -94.5786),
    ("Dallas", "TX", "-05:00", 32.7767, -96.7970),
    ("Houston", "TX", "-05:00", 29.7604, -95.3698),
    ("San Antonio", "TX", "-05:00", 29.4241, -98.4936),
    ("Austin", "TX", "-05:00", 30.2672, -97.7431),
    ("Oklahoma City", "OK", "-05:00", 35.4676, -97.5164),
    ("New Orleans", "LA", "-05:00", 29.9511, -90.0715),
    ("Denver", "CO", "-06:00", 39.7392, -104.9903),
    ("Salt Lake City", "UT", "-06:00", 40.7608, -111.8910),
    ("Phoenix", "AZ", "-07:00", 33.4484, -112.0740),
    ("Albuquerque", "NM", "-06:00", 35.0844, -106.6504),
    ("Las Vegas", "NV", "-07:00", 36.1699, -115.1398),
    ("Seattle", "WA", "-07:00", 47.6062, -122.3321),
    ("Portland", "OR", "-07:00", 45.5152, -122.6784),
    ("San Francisco", "CA", "-07:00", 37.7749, -122.4194),
    ("Los Angeles", "CA", "-07:00", 34.0522, -118.2437),
]

_NS = uuid.UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8")


def det_id(*parts: str) -> str:
    """Deterministic UUIDv5 id from string parts."""
    return str(uuid.uuid5(_NS, ":".join(parts)))


def weekdays(start: date, weeks: int) -> list[date]:
    days: list[date] = []
    d = start
    for _ in range(weeks * 7):
        if d.weekday() < 5:  # Mon–Fri
            days.append(d)
        d += timedelta(days=1)
    return days


def load_patient_ids(limit: int | None = None) -> list[str]:
    ids: list[str] = []
    with PATIENT_NDJSON.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            ids.append(json.loads(line)["id"])
            if limit is not None and len(ids) >= limit:
                break
    return ids


def build_location(idx: int, city: str, state: str, lat: float, lon: float) -> dict:
    npi = f"{9000000000 + idx:010d}"
    loc_id = det_id("location", npi)
    site_no = 100 + idx
    return {
        "resourceType": "Location",
        "id": loc_id,
        "meta": {"tag": [SYNTHETIC_TAG]},
        "identifier": [
            {"system": "https://parkerapex.com/atlas/location", "value": f"ATLAS-LOC-{site_no}"},
            {"system": "http://hl7.org/fhir/sid/us-npi", "value": npi},
        ],
        "status": "active",
        "name": f"Apex Atlas Community Clinic — {city}",
        "telecom": [
            {"system": "phone", "value": f"1-800-555-{2000 + idx:04d}", "use": "work"},
            {"system": "url", "value": f"https://booking.example.org/{loc_id}", "use": "work"},
        ],
        "address": {
            "use": "work",
            "line": [f"{100 + idx} Health Plaza"],
            "city": city,
            "state": state,
            "postalCode": f"{10000 + idx * 37:05d}",
            "country": "US",
        },
        "position": {"latitude": lat, "longitude": lon},
    }


def build_schedule(location: dict, svc: dict) -> dict:
    sched_id = det_id("schedule", location["id"], svc["key"])
    return {
        "resourceType": "Schedule",
        "id": sched_id,
        "meta": {"tag": [SYNTHETIC_TAG]},
        "serviceCategory": [
            {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/service-category",
                        "code": svc["category"]["code"],
                        "display": svc["category"]["display"],
                    }
                ]
            }
        ],
        "serviceType": [{"coding": [svc["coding"]], "text": svc["coding"]["display"]}],
        "actor": [{"reference": f"Location/{location['id']}"}],
        "planningHorizon": {
            "start": f"{WINDOW_START.isoformat()}T00:00:00Z",
            "end": f"{(WINDOW_START + timedelta(weeks=WINDOW_WEEKS)).isoformat()}T00:00:00Z",
        },
    }


def build_slot(schedule: dict, location: dict, svc: dict, start_dt: datetime, tz: str, status: str) -> dict:
    end_dt = start_dt + timedelta(minutes=SLOT_MINUTES)
    start_s = start_dt.isoformat() + tz
    end_s = end_dt.isoformat() + tz
    slot_id = det_id("slot", schedule["id"], start_s)
    booking_url = f"https://booking.example.org/{location['id']}/{svc['key']}?slot={slot_id}"
    return {
        "resourceType": "Slot",
        "id": slot_id,
        "meta": {"tag": [SYNTHETIC_TAG]},
        "extension": [
            {"url": f"{SMART_EXT}/booking-deep-link", "valueUrl": booking_url},
            {"url": f"{SMART_EXT}/booking-phone", "valueString": location["telecom"][0]["value"]},
            {"url": f"{SMART_EXT}/slot-capacity", "valueInteger": 1},
        ],
        "schedule": {"reference": f"Schedule/{schedule['id']}"},
        "serviceType": [{"coding": [svc["coding"]], "text": svc["coding"]["display"]}],
        "status": status,
        "start": start_s,
        "end": end_s,
    }


def build_appointment(slot: dict, schedule: dict, location: dict, svc: dict, patient_id: str) -> dict:
    appt_id = det_id("appointment", slot["id"], patient_id)
    return {
        "resourceType": "Appointment",
        "id": appt_id,
        "meta": {"tag": [SYNTHETIC_TAG]},
        "status": "booked",
        "serviceCategory": schedule["serviceCategory"],
        "serviceType": [{"coding": [svc["coding"]], "text": svc["coding"]["display"]}],
        "minutesDuration": svc["minutes"],
        "slot": [{"reference": f"Slot/{slot['id']}"}],
        "start": slot["start"],
        "end": slot["end"],
        "created": TRANSACTION_TIME,
        "participant": [
            {
                "actor": {"reference": f"Patient/{patient_id}"},
                "status": "accepted",
                "required": "required",
            },
            {
                "actor": {"reference": f"Location/{location['id']}", "display": location["name"]},
                "status": "accepted",
                "required": "required",
            },
        ],
    }


def write_ndjson(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")


def main() -> None:
    rng = random.Random(SEED)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    patient_ids = load_patient_ids()
    days = weekdays(WINDOW_START, WINDOW_WEEKS)

    locations: list[dict] = []
    schedules: list[dict] = []
    slots: list[dict] = []
    appointments: list[dict] = []

    for idx, (city, state, tz, lat, lon) in enumerate(CITIES):
        location = build_location(idx, city, state, lat, lon)
        locations.append(location)
        for svc in SERVICE_TYPES:
            schedule = build_schedule(location, svc)
            schedules.append(schedule)
            for day in days:
                for hour in SLOT_HOURS:
                    start_dt = datetime.combine(day, time(hour=hour))
                    booked = rng.random() < BOOKED_FRACTION
                    status = "busy" if booked else "free"
                    slot = build_slot(schedule, location, svc, start_dt, tz, status)
                    slots.append(slot)
                    if booked:
                        patient_id = rng.choice(patient_ids)
                        appointments.append(
                            build_appointment(slot, schedule, location, svc, patient_id)
                        )

    write_ndjson(OUT_DIR / "Location.ndjson", locations)
    write_ndjson(OUT_DIR / "Schedule.ndjson", schedules)
    write_ndjson(OUT_DIR / "Slot.ndjson", slots)
    write_ndjson(OUT_DIR / "Appointment.ndjson", appointments)

    manifest = {
        "transactionTime": TRANSACTION_TIME,
        "request": f"{PUBLISH_BASE}/$bulk-publish",
        "output": [
            {"type": "Location", "url": f"{PUBLISH_BASE}/Location.ndjson"},
            {"type": "Schedule", "url": f"{PUBLISH_BASE}/Schedule.ndjson"},
            {"type": "Slot", "url": f"{PUBLISH_BASE}/Slot.ndjson"},
        ],
        "error": [],
    }
    (OUT_DIR / "bulk-publish-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    free = sum(1 for s in slots if s["status"] == "free")
    print(
        f"Locations={len(locations)} Schedules={len(schedules)} "
        f"Slots={len(slots)} (free={free}, busy={len(slots) - free}) "
        f"Appointments={len(appointments)}"
    )


if __name__ == "__main__":
    main()

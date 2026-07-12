"""
SMART Scheduling Links dataset generation.

Produces a synthetic appointment-availability dataset conforming to the
SMART Scheduling Links specification
(https://github.com/smart-on-fhir/smart-scheduling-links) — the "SMART FHIR
Scheduling" `$bulk-publish` flow used to advertise open, bookable appointment
slots to consumer scheduling apps.

The public entry point is :func:`generate_scheduling_dataset`, which returns a
:class:`SchedulingDataset` of Location / Schedule / Slot resources (plus
optional Appointment bookings). Serialization to the `$bulk-publish` manifest
and NDJSON files lives in :mod:`parker_atlas.scheduling.publish`.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from parker_atlas.fhir.appointment import build_appointment_resource
from parker_atlas.fhir.location import build_scheduling_location_resource
from parker_atlas.fhir.schedule import build_schedule_resource
from parker_atlas.fhir.slot import build_slot_resource, slot_id
from parker_atlas.modules.runtime import Coding

SERVICE_TYPE_SYSTEM = "http://terminology.hl7.org/CodeSystem/service-type"


@dataclass(frozen=True, slots=True)
class ServiceType:
    """A bookable service offered on a Schedule."""

    key: str
    type_code: str
    type_display: str
    category_code: str
    category_display: str
    minutes: int

    @property
    def coding(self) -> Coding:
        return Coding(system=SERVICE_TYPE_SYSTEM, code=self.type_code, display=self.type_display)


# Service-type / service-category codes drawn from the FHIR value sets
# (http://hl7.org/fhir/ValueSet/service-type, .../service-category).
SERVICE_TYPES: dict[str, ServiceType] = {
    "general-practice": ServiceType(
        key="general-practice",
        type_code="124",
        type_display="General Practice",
        category_code="17",
        category_display="General Practice",
        minutes=30,
    ),
    "immunization": ServiceType(
        key="immunization",
        type_code="57",
        type_display="Immunization",
        category_code="31",
        category_display="Specialist Medical Services",
        minutes=15,
    ),
    "mental-health": ServiceType(
        key="mental-health",
        type_code="47",
        type_display="Mental Health",
        category_code="8",
        category_display="Counselling",
        minutes=45,
    ),
}

DEFAULT_SERVICE_KEYS = ("general-practice", "immunization")


@dataclass(frozen=True, slots=True)
class ClinicSite:
    """A physical clinic site the dataset publishes availability for."""

    city: str
    state: str
    tz_offset: str  # e.g. "-04:00" (US July / DST)
    latitude: float
    longitude: float


# 40 synthetic clinic sites across 24 states. Timezone offsets are July (DST).
CLINIC_SITES: tuple[ClinicSite, ...] = (
    ClinicSite("Boston", "MA", "-04:00", 42.3601, -71.0589),
    ClinicSite("Worcester", "MA", "-04:00", 42.2626, -71.8023),
    ClinicSite("New York", "NY", "-04:00", 40.7128, -74.0060),
    ClinicSite("Buffalo", "NY", "-04:00", 42.8864, -78.8784),
    ClinicSite("Philadelphia", "PA", "-04:00", 39.9526, -75.1652),
    ClinicSite("Pittsburgh", "PA", "-04:00", 40.4406, -79.9959),
    ClinicSite("Baltimore", "MD", "-04:00", 39.2904, -76.6122),
    ClinicSite("Washington", "DC", "-04:00", 38.9072, -77.0369),
    ClinicSite("Richmond", "VA", "-04:00", 37.5407, -77.4360),
    ClinicSite("Charlotte", "NC", "-04:00", 35.2271, -80.8431),
    ClinicSite("Atlanta", "GA", "-04:00", 33.7490, -84.3880),
    ClinicSite("Miami", "FL", "-04:00", 25.7617, -80.1918),
    ClinicSite("Orlando", "FL", "-04:00", 28.5383, -81.3792),
    ClinicSite("Tampa", "FL", "-04:00", 27.9506, -82.4572),
    ClinicSite("Nashville", "TN", "-05:00", 36.1627, -86.7816),
    ClinicSite("Memphis", "TN", "-05:00", 35.1495, -90.0490),
    ClinicSite("Columbus", "OH", "-04:00", 39.9612, -82.9988),
    ClinicSite("Cleveland", "OH", "-04:00", 41.4993, -81.6944),
    ClinicSite("Detroit", "MI", "-04:00", 42.3314, -83.0458),
    ClinicSite("Indianapolis", "IN", "-04:00", 39.7684, -86.1581),
    ClinicSite("Chicago", "IL", "-05:00", 41.8781, -87.6298),
    ClinicSite("Milwaukee", "WI", "-05:00", 43.0389, -87.9065),
    ClinicSite("Minneapolis", "MN", "-05:00", 44.9778, -93.2650),
    ClinicSite("St. Louis", "MO", "-05:00", 38.6270, -90.1994),
    ClinicSite("Kansas City", "MO", "-05:00", 39.0997, -94.5786),
    ClinicSite("Dallas", "TX", "-05:00", 32.7767, -96.7970),
    ClinicSite("Houston", "TX", "-05:00", 29.7604, -95.3698),
    ClinicSite("San Antonio", "TX", "-05:00", 29.4241, -98.4936),
    ClinicSite("Austin", "TX", "-05:00", 30.2672, -97.7431),
    ClinicSite("Oklahoma City", "OK", "-05:00", 35.4676, -97.5164),
    ClinicSite("New Orleans", "LA", "-05:00", 29.9511, -90.0715),
    ClinicSite("Denver", "CO", "-06:00", 39.7392, -104.9903),
    ClinicSite("Salt Lake City", "UT", "-06:00", 40.7608, -111.8910),
    ClinicSite("Phoenix", "AZ", "-07:00", 33.4484, -112.0740),
    ClinicSite("Albuquerque", "NM", "-06:00", 35.0844, -106.6504),
    ClinicSite("Las Vegas", "NV", "-07:00", 36.1699, -115.1398),
    ClinicSite("Seattle", "WA", "-07:00", 47.6062, -122.3321),
    ClinicSite("Portland", "OR", "-07:00", 45.5152, -122.6784),
    ClinicSite("San Francisco", "CA", "-07:00", 37.7749, -122.4194),
    ClinicSite("Los Angeles", "CA", "-07:00", 34.0522, -118.2437),
)


@dataclass(slots=True)
class SchedulingConfig:
    """Parameters controlling a SMART Scheduling Links dataset."""

    sites: int = 25
    service_keys: tuple[str, ...] = DEFAULT_SERVICE_KEYS
    # Defaults to the day the config is constructed (not import time).
    window_start: date = field(default_factory=date.today)
    weeks: int = 2
    day_start_hour: int = 8
    day_end_hour: int = 17
    slot_minutes: int = 60
    booked_fraction: float = 0.20
    seed: int | None = None
    booking_base_url: str = "https://booking.example.org"

    def validate(self) -> None:
        if not 1 <= self.sites <= len(CLINIC_SITES):
            raise ValueError(f"sites must be between 1 and {len(CLINIC_SITES)}")
        if self.weeks < 1:
            raise ValueError("weeks must be >= 1")
        if not 0 <= self.day_start_hour < self.day_end_hour <= 24:
            raise ValueError("require 0 <= day_start_hour < day_end_hour <= 24")
        if self.slot_minutes <= 0 or (60 % self.slot_minutes and self.slot_minutes % 60):
            raise ValueError("slot_minutes must be a positive divisor/multiple of an hour")
        if not 0.0 <= self.booked_fraction <= 1.0:
            raise ValueError("booked_fraction must be between 0 and 1")
        for key in self.service_keys:
            if key not in SERVICE_TYPES:
                raise ValueError(
                    f"unknown service type {key!r}; known: {sorted(SERVICE_TYPES)}"
                )
        if not self.service_keys:
            raise ValueError("at least one service type is required")


@dataclass(slots=True)
class SchedulingDataset:
    """The generated SMART Scheduling Links resources."""

    locations: list[dict] = field(default_factory=list)
    schedules: list[dict] = field(default_factory=list)
    slots: list[dict] = field(default_factory=list)
    appointments: list[dict] = field(default_factory=list)

    @property
    def counts(self) -> dict[str, int]:
        free = sum(1 for s in self.slots if s["status"] == "free")
        return {
            "Location": len(self.locations),
            "Schedule": len(self.schedules),
            "Slot": len(self.slots),
            "Slot(free)": free,
            "Slot(busy)": len(self.slots) - free,
            "Appointment": len(self.appointments),
        }


def _weekdays(start: date, weeks: int) -> list[date]:
    days: list[date] = []
    d = start
    for _ in range(weeks * 7):
        if d.weekday() < 5:  # Mon-Fri
            days.append(d)
        d += timedelta(days=1)
    return days


def _slot_starts(day: date, cfg: SchedulingConfig) -> list[datetime]:
    starts: list[datetime] = []
    cursor = datetime.combine(day, time(hour=cfg.day_start_hour))
    end_of_day = datetime.combine(day, time(hour=0)) + timedelta(hours=cfg.day_end_hour)
    while cursor < end_of_day:
        starts.append(cursor)
        cursor += timedelta(minutes=cfg.slot_minutes)
    return starts


def generate_scheduling_dataset(
    config: SchedulingConfig,
    patient_ids: list[str] | None = None,
    *,
    created: str | None = None,
) -> SchedulingDataset:
    """Generate a SMART Scheduling Links dataset from ``config``.

    When ``patient_ids`` is provided, each ``busy`` slot is booked with an
    Appointment referencing a randomly-chosen patient. Without patient ids the
    slots are still marked ``free``/``busy`` per ``booked_fraction`` but no
    Appointment resources are emitted.
    """
    config.validate()
    rng = random.Random(config.seed)
    days = _weekdays(config.window_start, config.weeks)
    horizon_start = f"{config.window_start.isoformat()}T00:00:00Z"
    horizon_end = f"{(config.window_start + timedelta(weeks=config.weeks)).isoformat()}T00:00:00Z"
    created = created or f"{config.window_start.isoformat()}T00:00:00Z"
    services = [SERVICE_TYPES[k] for k in config.service_keys]

    dataset = SchedulingDataset()

    for idx, site in enumerate(CLINIC_SITES[: config.sites]):
        identifier_value = f"ATLAS-LOC-{100 + idx}"
        npi = f"{9000000000 + idx:010d}"
        phone = f"1-800-555-{2000 + idx:04d}"
        location = build_scheduling_location_resource(
            identifier_value=identifier_value,
            name=f"Apex Atlas Community Clinic — {site.city}",
            line=f"{100 + idx} Health Plaza",
            city=site.city,
            state=site.state,
            postal_code=f"{10000 + idx * 37:05d}",
            latitude=site.latitude,
            longitude=site.longitude,
            phone=phone,
            url=f"{config.booking_base_url}/locations/{identifier_value}",
            npi=npi,
        )
        dataset.locations.append(location)
        loc_id = location["id"]

        for svc in services:
            schedule = build_schedule_resource(
                location_id=loc_id,
                service_key=svc.key,
                service_type=svc.coding,
                service_category_code=svc.category_code,
                service_category_display=svc.category_display,
                horizon_start=horizon_start,
                horizon_end=horizon_end,
            )
            dataset.schedules.append(schedule)
            sched_id = schedule["id"]

            for day in days:
                for start_dt in _slot_starts(day, config):
                    start_s = start_dt.isoformat() + site.tz_offset
                    end_s = (start_dt + timedelta(minutes=config.slot_minutes)).isoformat() + site.tz_offset
                    booked = rng.random() < config.booked_fraction
                    status = "busy" if booked else "free"
                    slot_id_value = slot_id(schedule_id=sched_id, start=start_s)
                    deep_link = f"{config.booking_base_url}/{loc_id}/{svc.key}?slot={slot_id_value}"
                    slot = build_slot_resource(
                        schedule_id=sched_id,
                        service_type=svc.coding,
                        start=start_s,
                        end=end_s,
                        status=status,
                        booking_deep_link=deep_link,
                        booking_phone=phone,
                        capacity=1,
                    )
                    dataset.slots.append(slot)

                    if booked and patient_ids:
                        patient_id = rng.choice(patient_ids)
                        appt = build_appointment_resource(
                            patient_id=patient_id,
                            slot_id=slot_id_value,
                            location_id=loc_id,
                            location_display=location["name"],
                            service_type=svc.coding,
                            service_category_code=svc.category_code,
                            service_category_display=svc.category_display,
                            start=start_s,
                            end=end_s,
                            minutes_duration=svc.minutes,
                            created=created,
                        )
                        dataset.appointments.append(appt)

    return dataset

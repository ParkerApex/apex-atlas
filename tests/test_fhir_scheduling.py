"""Tests for the SMART Scheduling Links FHIR builders."""

from __future__ import annotations

import pytest
from fhir.resources.R4B.appointment import Appointment
from fhir.resources.R4B.location import Location
from fhir.resources.R4B.schedule import Schedule
from fhir.resources.R4B.slot import Slot

from parker_atlas.fhir.appointment import appointment_id, build_appointment_resource
from parker_atlas.fhir.location import (
    build_scheduling_location_resource,
    scheduling_location_id,
)
from parker_atlas.fhir.schedule import build_schedule_resource, schedule_id
from parker_atlas.fhir.slot import (
    BOOKING_DEEP_LINK_EXT,
    BOOKING_PHONE_EXT,
    SLOT_CAPACITY_EXT,
    build_slot_resource,
    slot_id,
)
from parker_atlas.modules.runtime import Coding

GP = Coding(
    system="http://terminology.hl7.org/CodeSystem/service-type",
    code="124",
    display="General Practice",
)


def _synthetic_tag(resource: dict) -> bool:
    return any(t["code"] == "HTEST" for t in resource["meta"]["tag"])


class TestSchedulingLocation:
    def test_builds_and_validates(self):
        loc = build_scheduling_location_resource(
            identifier_value="ATLAS-LOC-100",
            name="Apex Atlas Community Clinic — Boston",
            line="100 Health Plaza",
            city="Boston",
            state="MA",
            postal_code="02101",
            latitude=42.3601,
            longitude=-71.0589,
            phone="1-800-555-2000",
            url="https://booking.example.org/locations/ATLAS-LOC-100",
            npi="9000000000",
        )
        Location(**loc)
        assert loc["position"] == {"latitude": 42.3601, "longitude": -71.0589}
        assert _synthetic_tag(loc)
        systems = {i["system"] for i in loc["identifier"]}
        assert "http://hl7.org/fhir/sid/us-npi" in systems

    def test_id_is_deterministic(self):
        assert scheduling_location_id(identifier_value="X") == scheduling_location_id(
            identifier_value="X"
        )
        assert scheduling_location_id(identifier_value="X") != scheduling_location_id(
            identifier_value="Y"
        )

    def test_optional_contact_omitted(self):
        loc = build_scheduling_location_resource(
            identifier_value="ATLAS-LOC-1",
            name="Clinic",
            line="1 Main",
            city="Austin",
            state="TX",
            postal_code="78701",
            latitude=30.2,
            longitude=-97.7,
        )
        Location(**loc)
        assert "telecom" not in loc


class TestSchedule:
    def test_actor_references_location(self):
        sched = build_schedule_resource(
            location_id="loc-1",
            service_key="general-practice",
            service_type=GP,
            service_category_code="17",
            service_category_display="General Practice",
            horizon_start="2026-07-13T00:00:00Z",
            horizon_end="2026-07-27T00:00:00Z",
        )
        Schedule(**sched)
        assert sched["actor"][0]["reference"] == "Location/loc-1"
        assert sched["serviceType"][0]["coding"][0]["code"] == "124"
        assert "planningHorizon" in sched

    def test_id_keyed_by_location_and_service(self):
        a = schedule_id(location_id="l", service_key="general-practice")
        b = schedule_id(location_id="l", service_key="immunization")
        assert a != b


class TestSlot:
    def _slot(self, status="free"):
        return build_slot_resource(
            schedule_id="sched-1",
            service_type=GP,
            start="2026-07-13T08:00:00-04:00",
            end="2026-07-13T09:00:00-04:00",
            status=status,
            booking_deep_link="https://booking.example.org/x?slot=1",
            booking_phone="1-800-555-2000",
            capacity=1,
        )

    def test_builds_with_smart_extensions(self):
        slot = self._slot()
        Slot(**slot)
        ext_urls = {e["url"] for e in slot["extension"]}
        assert ext_urls == {BOOKING_DEEP_LINK_EXT, BOOKING_PHONE_EXT, SLOT_CAPACITY_EXT}
        assert slot["schedule"]["reference"] == "Schedule/sched-1"

    def test_rejects_bad_status(self):
        with pytest.raises(ValueError):
            build_slot_resource(
                schedule_id="s",
                service_type=GP,
                start="2026-07-13T08:00:00-04:00",
                end="2026-07-13T09:00:00-04:00",
                status="open",
            )

    def test_extensions_omitted_when_absent(self):
        slot = build_slot_resource(
            schedule_id="s",
            service_type=GP,
            start="2026-07-13T08:00:00-04:00",
            end="2026-07-13T09:00:00-04:00",
        )
        Slot(**slot)
        assert "extension" not in slot

    def test_id_keyed_by_schedule_and_start(self):
        a = slot_id(schedule_id="s", start="2026-07-13T08:00:00-04:00")
        b = slot_id(schedule_id="s", start="2026-07-13T09:00:00-04:00")
        assert a != b


class TestAppointment:
    def test_books_patient_into_slot(self):
        appt = build_appointment_resource(
            patient_id="GPX-SYN-0000000001-8",
            slot_id="slot-1",
            location_id="loc-1",
            location_display="Clinic",
            service_type=GP,
            service_category_code="17",
            service_category_display="General Practice",
            start="2026-07-13T08:00:00-04:00",
            end="2026-07-13T09:00:00-04:00",
            minutes_duration=30,
            created="2026-07-12T00:00:00Z",
        )
        Appointment(**appt)
        refs = {p["actor"]["reference"] for p in appt["participant"]}
        assert refs == {"Patient/GPX-SYN-0000000001-8", "Location/loc-1"}
        assert appt["slot"][0]["reference"] == "Slot/slot-1"
        assert appt["status"] == "booked"

    def test_id_keyed_by_slot_and_patient(self):
        a = appointment_id(slot_id="s", patient_id="p1")
        b = appointment_id(slot_id="s", patient_id="p2")
        assert a != b

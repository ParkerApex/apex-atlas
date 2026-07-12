"""Tests for the SMART Scheduling Links dataset generator and manifest."""

from __future__ import annotations

from datetime import date

import pytest
from fhir.resources.R4B.appointment import Appointment
from fhir.resources.R4B.location import Location
from fhir.resources.R4B.schedule import Schedule
from fhir.resources.R4B.slot import Slot

from parker_atlas.scheduling import (
    CLINIC_SITES,
    SchedulingConfig,
    build_manifest,
    generate_scheduling_dataset,
    write_bulk_publish,
)

WINDOW = date(2026, 7, 13)  # a Monday


def _cfg(**kw) -> SchedulingConfig:
    base = {
        "sites": 3,
        "weeks": 1,
        "seed": 7,
        "window_start": WINDOW,
        "booked_fraction": 0.25,
        **kw,
    }
    return SchedulingConfig(**base)


class TestGeneration:
    def test_counts_and_structure(self):
        ds = generate_scheduling_dataset(_cfg())
        c = ds.counts
        assert c["Location"] == 3
        assert c["Schedule"] == 3 * 2  # two default services
        # 5 weekdays * 9 hourly slots * 6 schedules
        assert c["Slot"] == 5 * 9 * 6
        assert c["Slot(free)"] + c["Slot(busy)"] == c["Slot"]

    def test_all_resources_validate(self):
        ds = generate_scheduling_dataset(_cfg(), patient_ids=["GPX-SYN-0000000001-8"])
        for r in ds.locations:
            Location(**r)
        for r in ds.schedules:
            Schedule(**r)
        for r in ds.slots:
            Slot(**r)
        for r in ds.appointments:
            Appointment(**r)

    def test_referential_integrity(self):
        ds = generate_scheduling_dataset(_cfg(), patient_ids=["GPX-SYN-0000000001-8"])
        loc_ids = {loc["id"] for loc in ds.locations}
        sched_ids = {s["id"] for s in ds.schedules}
        slot_ids = {s["id"] for s in ds.slots}
        for s in ds.schedules:
            assert s["actor"][0]["reference"].split("/")[1] in loc_ids
        for s in ds.slots:
            assert s["schedule"]["reference"].split("/")[1] in sched_ids
        for a in ds.appointments:
            assert a["slot"][0]["reference"].split("/")[1] in slot_ids

    def test_appointments_only_with_patients(self):
        assert generate_scheduling_dataset(_cfg()).appointments == []
        ds = generate_scheduling_dataset(_cfg(), patient_ids=["GPX-SYN-0000000001-8"])
        # one appointment per busy slot
        assert len(ds.appointments) == ds.counts["Slot(busy)"]

    def test_appointment_patients_come_from_pool(self):
        pool = ["GPX-SYN-0000000001-8", "GPX-SYN-0000000002-6"]
        ds = generate_scheduling_dataset(_cfg(), patient_ids=pool)
        for a in ds.appointments:
            ref = next(
                p["actor"]["reference"]
                for p in a["participant"]
                if p["actor"]["reference"].startswith("Patient/")
            )
            assert ref.split("/", 1)[1] in pool

    def test_deterministic_with_seed(self):
        a = generate_scheduling_dataset(_cfg(seed=42))
        b = generate_scheduling_dataset(_cfg(seed=42))
        assert [s["status"] for s in a.slots] == [s["status"] for s in b.slots]

    def test_slots_only_on_weekdays(self):
        ds = generate_scheduling_dataset(_cfg(weeks=1))
        for s in ds.slots:
            # start is "YYYY-MM-DDThh:..." — weekday() < 5
            d = date.fromisoformat(s["start"][:10])
            assert d.weekday() < 5


class TestConfigValidation:
    @pytest.mark.parametrize(
        "kw",
        [
            {"sites": 0},
            {"sites": len(CLINIC_SITES) + 1},
            {"weeks": 0},
            {"booked_fraction": 1.5},
            {"day_start_hour": 17, "day_end_hour": 8},
            {"service_keys": ("nonexistent",)},
            {"service_keys": ()},
        ],
    )
    def test_invalid_configs_raise(self, kw):
        with pytest.raises(ValueError):
            generate_scheduling_dataset(_cfg(**kw))


class TestManifest:
    def test_manifest_shape(self):
        ds = generate_scheduling_dataset(_cfg())
        m = build_manifest(
            ds, base_url="https://x/scheduling/", transaction_time="2026-07-12T00:00:00Z"
        )
        assert m["request"] == "https://x/scheduling/$bulk-publish"
        assert [o["type"] for o in m["output"]] == ["Location", "Schedule", "Slot"]
        assert m["output"][0]["url"] == "https://x/scheduling/Location.ndjson"
        assert m["error"] == []


class TestWriteBulkPublish:
    def test_writes_files(self, tmp_path):
        ds = generate_scheduling_dataset(_cfg(), patient_ids=["GPX-SYN-0000000001-8"])
        manifest_path = write_bulk_publish(
            ds,
            tmp_path,
            base_url="https://x/scheduling",
            transaction_time="2026-07-12T00:00:00Z",
        )
        assert manifest_path.exists()
        for name in ("Location", "Schedule", "Slot", "Appointment"):
            f = tmp_path / f"{name}.ndjson"
            assert f.exists()
            assert f.read_text().strip()

    def test_no_appointment_file_without_bookings(self, tmp_path):
        ds = generate_scheduling_dataset(_cfg())
        write_bulk_publish(
            ds, tmp_path, base_url="https://x", transaction_time="2026-07-12T00:00:00Z"
        )
        assert not (tmp_path / "Appointment.ndjson").exists()

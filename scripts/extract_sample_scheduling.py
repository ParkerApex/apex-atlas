"""Extract readable examples from the CMS Connectathon 2026 SMART Scheduling
Links (`$bulk-publish`) dataset.

The published `Slot.ndjson` is large and awkward to read by hand. This script
pulls out a small, self-contained slice centered on a single clinic and writes:

- Per-resource-type sample arrays (``Location.example.json``,
  ``Schedule.example.json``, ``Slot.example.json``, ``Appointment.example.json``)
  — pretty-printed JSON arrays of a few real resources so you can see the shape
  of each type without opening the NDJSON.
- ``clinic-availability.example.json`` — one self-contained FHIR **collection
  Bundle** for that clinic: Location → Schedules → a handful of Slots
  (free and booked) → the Appointments that booked them → the referenced
  Patients (drawn from the 20,000-patient population). Read one file to see the
  whole scheduling ↔ patient graph.

Output goes to ``samples/cms-connectathon-2026/scheduling/examples/``.

Run:

    python scripts/extract_sample_scheduling.py
"""

from __future__ import annotations

import json
from pathlib import Path

from fhir.resources.R4B.bundle import Bundle as _Bundle

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHED_DIR = REPO_ROOT / "samples" / "cms-connectathon-2026" / "scheduling"
PATIENTS_NDJSON = (
    REPO_ROOT / "samples" / "cms-connectathon-2026" / "patients" / "Patient.ndjson"
)
OUT_DIR = SCHED_DIR / "examples"

# Example base for the collection Bundle so relative references resolve.
FHIR_BASE = "https://parkerapex.com/atlas/fhir"
# Slots to show per schedule, per status, in the readable slice.
FREE_PER_SCHEDULE = 2
BUSY_PER_SCHEDULE = 2


def load_ndjson(path: Path):
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    locations = list(load_ndjson(SCHED_DIR / "Location.ndjson"))
    schedules = list(load_ndjson(SCHED_DIR / "Schedule.ndjson"))

    # Anchor the example on the first clinic.
    location = locations[0]
    loc_id = location["id"]
    clinic_schedules = [
        s for s in schedules if any(a["reference"] == f"Location/{loc_id}" for a in s["actor"])
    ]
    sched_ids = {s["id"] for s in clinic_schedules}

    # Collect a small, readable set of slots: a few free + a few booked per
    # schedule, in file order.
    free: dict[str, list[dict]] = {sid: [] for sid in sched_ids}
    busy: dict[str, list[dict]] = {sid: [] for sid in sched_ids}
    for slot in load_ndjson(SCHED_DIR / "Slot.ndjson"):
        sid = slot["schedule"]["reference"].split("/", 1)[1]
        if sid not in sched_ids:
            continue
        bucket = free if slot["status"] == "free" else busy
        cap = FREE_PER_SCHEDULE if slot["status"] == "free" else BUSY_PER_SCHEDULE
        if len(bucket[sid]) < cap:
            bucket[sid].append(slot)
        if all(
            len(free[x]) >= FREE_PER_SCHEDULE and len(busy[x]) >= BUSY_PER_SCHEDULE
            for x in sched_ids
        ):
            break

    example_slots = [s for sid in sched_ids for s in free[sid] + busy[sid]]
    booked_slot_ids = {s["id"] for sid in sched_ids for s in busy[sid]}

    # Appointments that booked those slots, and the patients they reference.
    example_appts: list[dict] = []
    needed_patient_ids: set[str] = set()
    for appt in load_ndjson(SCHED_DIR / "Appointment.ndjson"):
        slot_id = appt["slot"][0]["reference"].split("/", 1)[1]
        if slot_id in booked_slot_ids:
            example_appts.append(appt)
            for part in appt["participant"]:
                ref = part["actor"]["reference"]
                if ref.startswith("Patient/"):
                    needed_patient_ids.add(ref.split("/", 1)[1])

    # Pull the referenced Patient resources from the population.
    patients: list[dict] = []
    if needed_patient_ids:
        for res in load_ndjson(PATIENTS_NDJSON):
            if res["id"] in needed_patient_ids:
                patients.append(res)
                if len(patients) == len(needed_patient_ids):
                    break

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Per-type readable arrays.
    write_json(OUT_DIR / "Location.example.json", [location])
    write_json(OUT_DIR / "Schedule.example.json", clinic_schedules)
    write_json(OUT_DIR / "Slot.example.json", example_slots)
    write_json(OUT_DIR / "Appointment.example.json", example_appts)

    # Self-contained walkthrough Bundle (collection).
    graph = [location, *clinic_schedules, *example_slots, *example_appts, *patients]
    bundle = {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            {"fullUrl": f"{FHIR_BASE}/{r['resourceType']}/{r['id']}", "resource": r}
            for r in graph
        ],
    }
    _Bundle.model_validate(bundle)
    write_json(OUT_DIR / "clinic-availability.example.json", bundle)

    _write_readme(location, clinic_schedules, example_slots, example_appts, patients)

    print(
        f"clinic={location['name']} schedules={len(clinic_schedules)} "
        f"slots={len(example_slots)} appointments={len(example_appts)} "
        f"patients={len(patients)}"
    )


def _write_readme(location, schedules, slots, appts, patients) -> None:
    free_n = sum(1 for s in slots if s["status"] == "free")
    busy_n = len(slots) - free_n
    services = ", ".join(
        s["serviceType"][0]["coding"][0]["display"] for s in schedules
    )
    body = (
        "# Sample scheduling records\n\n"
        "Readable, pretty-printed samples of the SMART Scheduling Links "
        "(`$bulk-publish`) dataset in [`../`](../). The published `Slot.ndjson` "
        "is large; these files let you see the shape of each resource, and how "
        "booked slots tie back to real patients from the 20,000-patient "
        "population, without opening the NDJSON.\n\n"
        "All records below are for a single example clinic — "
        f"**{location['name']}** ({location['address']['city']}, "
        f"{location['address']['state']}), offering: {services}.\n\n"
        "## Files\n\n"
        "| File | What it shows |\n| --- | --- |\n"
        "| `Location.example.json` | The clinic `Location` (address, geo `position`, identifiers). |\n"
        f"| `Schedule.example.json` | Its {len(schedules)} `Schedule`s (one per service type; `actor` → Location). |\n"
        f"| `Slot.example.json` | {len(slots)} `Slot`s ({free_n} free, {busy_n} booked) with the SMART `booking-deep-link` / `booking-phone` / `slot-capacity` extensions. |\n"
        f"| `Appointment.example.json` | The {len(appts)} `Appointment`s that booked those slots, referencing real patients. |\n"
        "| `clinic-availability.example.json` | A single self-contained FHIR **collection Bundle** stitching the whole graph together: Location → Schedules → Slots → Appointments → Patients. |\n\n"
        "## Reference graph\n\n"
        "```\n"
        "Location  <-actor-  Schedule  <-schedule-  Slot  <-slot-  Appointment  -participant->  Patient (GPX-SYN-...)\n"
        "```\n\n"
        f"The {len(appts)} booked appointments here reference these patients from "
        "the population: "
        + ", ".join(f"`{p['id']}`" for p in patients)
        + ".\n\nRegenerate with `python scripts/extract_sample_scheduling.py`.\n"
    )
    (OUT_DIR / "README.md").write_text(body, encoding="utf-8")


if __name__ == "__main__":
    main()

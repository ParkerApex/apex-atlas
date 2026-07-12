# Sample scheduling records

Readable, pretty-printed samples of the SMART Scheduling Links (`$bulk-publish`) dataset in [`../`](../). The published `Slot.ndjson` is large; these files let you see the shape of each resource, and how booked slots tie back to real patients from the 20,000-patient population, without opening the NDJSON.

All records below are for a single example clinic — **Apex Atlas Community Clinic — Boston** (Boston, MA), offering: General Practice, Immunization.

## Files

| File | What it shows |
| --- | --- |
| `Location.example.json` | The clinic `Location` (address, geo `position`, identifiers). |
| `Schedule.example.json` | Its 2 `Schedule`s (one per service type; `actor` → Location). |
| `Slot.example.json` | 8 `Slot`s (4 free, 4 booked) with the SMART `booking-deep-link` / `booking-phone` / `slot-capacity` extensions. |
| `Appointment.example.json` | The 4 `Appointment`s that booked those slots, referencing real patients. |
| `clinic-availability.example.json` | A single self-contained FHIR **collection Bundle** stitching the whole graph together: Location → Schedules → Slots → Appointments → Patients. |

## Reference graph

```
Location  ←actor–  Schedule  ←schedule–  Slot  ←slot–  Appointment  –participant→  Patient (GPX-SYN-…)
```

The 4 booked appointments here reference these patients from the population: `GPX-SYN-0000005895-8`, `GPX-SYN-0000011977-6`, `GPX-SYN-0000012487-5`, `GPX-SYN-0000015546-5`.

Regenerate with `python scripts/extract_sample_scheduling.py`.

# SMART Scheduling Links (`$bulk-publish`)

Apex Atlas can publish synthetic **appointment availability** as a
[SMART Scheduling Links](https://github.com/smart-on-fhir/smart-scheduling-links)
dataset — the "SMART FHIR Scheduling" `$bulk-publish` flow that advertises open,
bookable appointment slots to consumer scheduling applications.

A published dataset is a JSON **manifest** plus one **NDJSON** file per resource
type:

| File | Resource | Role |
| --- | --- | --- |
| `bulk-publish-manifest.json` | — | The document a server returns from its `$bulk-publish` operation. Its `output[]` array links the NDJSON files. |
| `Location.ndjson` | Location | Physical clinic sites, with `position` (lat/long), address, telecom, and NPI identifiers. |
| `Schedule.ndjson` | Schedule | One per (Location × service type). `actor` → Location. |
| `Slot.ndjson` | Slot | Bookable windows (`free`/`busy`) referencing a Schedule, with the SMART `booking-deep-link`, `booking-phone`, and `slot-capacity` extensions. |
| `Appointment.ndjson` | Appointment | *(optional)* Booked slots tied to patients. Not part of the SMART Scheduling Links payload; emitted only when `--patients` is supplied. |

All resources carry the `HTEST` (“test health data”) `meta.tag` and validate
against the `fhir.resources` R4B models.

## CLI

```bash
atlas publish-scheduling [OPTIONS]
```

| Option | Default | Description |
| --- | --- | --- |
| `--out`, `-o` | `./scheduling` | Output directory. |
| `--sites` | `25` | Number of clinic Locations to publish (1–40). |
| `--service-types` | `general-practice,immunization` | Comma-separated: `general-practice`, `immunization`, `mental-health`. |
| `--window-start` | today | ISO date the availability window opens. |
| `--weeks` | `2` | Weeks of availability (weekdays only). |
| `--day-start-hour` / `--day-end-hour` | `8` / `17` | Local booking hours. |
| `--slot-minutes` | `60` | Slot length. |
| `--booked-fraction` | `0.20` | Fraction of slots marked `busy`. |
| `--seed` | — | RNG seed for reproducibility. |
| `--base-url` | `https://example.org/scheduling` | Base URL advertised in the manifest `output[]`. |
| `--booking-base-url` | `https://booking.example.org` | Base URL for per-slot booking deep links. |
| `--patients` | — | `Patient.ndjson` file or cohort dir; booked slots get Appointments referencing these patients. |

### Examples

```bash
# 25 clinics, two weeks of weekday availability.
atlas publish-scheduling --sites 25 --weeks 2 --seed 42 --out ./scheduling

# Book a subset of an existing cohort into busy slots.
atlas generate --patients 2000 --seed 42 --format ndjson --out ./cohort
atlas publish-scheduling --sites 25 --weeks 2 --seed 42 \
  --patients ./cohort/Patient.ndjson --out ./scheduling
```

## Dev API

`atlas serve` exposes the same feature over HTTP (deterministic, capped for the
dev server at 10 sites / 4 weeks):

```
GET /scheduling/$bulk-publish?sites=8&weeks=2&seed=0&services=general-practice,immunization
GET /scheduling/Location.ndjson?<same params>
GET /scheduling/Schedule.ndjson?<same params>
GET /scheduling/Slot.ndjson?<same params>
```

The manifest's `output[]` URLs point back at the `/scheduling/<Type>.ndjson`
routes. Generation is deterministic for a given `seed`, so a client can fetch
the manifest and then stream each file consistently.

## Python API

```python
from datetime import date
from parker_atlas.scheduling import (
    SchedulingConfig, generate_scheduling_dataset, write_bulk_publish,
)

config = SchedulingConfig(sites=25, weeks=2, seed=42, window_start=date(2026, 7, 13))
dataset = generate_scheduling_dataset(config, patient_ids=["GPX-SYN-0000000001-8"])
write_bulk_publish(
    dataset, out_dir=Path("./scheduling"),
    base_url="https://example.org/scheduling",
    transaction_time="2026-07-12T00:00:00Z",
)
```

## Referential graph

```
Slot.schedule            → Schedule
Schedule.actor           → Location
Appointment.slot         → Slot
Appointment.participant  → Patient/GPX-SYN-…, Location
```

## Service types

Codes are drawn from the FHIR
[`service-type`](http://hl7.org/fhir/ValueSet/service-type) and
[`service-category`](http://hl7.org/fhir/ValueSet/service-category) value sets:

| Key | service-type | Default slot booking |
| --- | --- | --- |
| `general-practice` | `124` General Practice | 30-min appointment duration |
| `immunization` | `57` Immunization | 15-min appointment duration |
| `mental-health` | `47` Mental Health | 45-min appointment duration |

## Provenance

Data is structurally synthetic (clinic sites, schedules, and slots are
fabricated). It is suitable for connectathons, integration testing, and demos —
not for representing real appointment availability.

# CMS Connectathon 2026 — Synthetic Bulk-Publish Dataset

Synthetic, license-clean FHIR R4 data prepared for the **CMS Connectathon 2026**.
Two independently usable datasets are published here:

1. **Patients** — a 20,000-patient population as FHIR Bulk Data (`$export`)-style NDJSON.
2. **Scheduling** — open appointment availability as a
   [SMART Scheduling Links](https://github.com/smart-on-fhir/smart-scheduling-links)
   (`$bulk-publish`) dataset, plus booked `Appointment` resources.

All records are synthetic. Every resource carries the
`HTEST` ("test health data") `meta.tag`. No record corresponds to a real
individual. See the repository [security & provenance FAQ](../../docs/security-provenance-faq.md).

---

## 1. Patients — FHIR Bulk Data (`$export`) NDJSON

Directory: [`patients/`](./patients/)

One NDJSON file per resource type, one resource per line — the FHIR
[Bulk Data Access](https://hl7.org/fhir/uv/bulkdata/) convention. Conforms to
US Core 6.1. Patient identity uses the Parker Global Patient Identifier
(`GPX-SYN-…`) under the synthetic namespace.

| File | Resources | Lines |
| --- | --- | ---: |
| `Patient.ndjson` | US Core Patient | 20,000 |
| `Condition.ndjson` | Problem-list conditions | 23,381 |
| `Encounter.ndjson` | Ambulatory / preventive encounters | 30,959 |
| `Observation.ndjson` | Vitals, labs, screenings | 45,626 |
| `MedicationRequest.ndjson` | Prescriptions | 6,268 |
| `Immunization.ndjson` | Vaccinations | 6,245 |
| `Coverage.ndjson` | Payer coverage | 18,227 |
| `Organization.ndjson` | Payer organizations | 7 |
| `InsurancePlan.ndjson` | Insurance plans | 7 |
| `generation-metadata.json` | Run manifest (seed, modules, flags) | — |

**Generation parameters:** `seed=2026`, modules `hypertension,diabetes,wellness`,
`--with-coverage`, US Core 6.1.

Regenerate:

```bash
atlas generate --patients 20000 --seed 2026 --format ndjson \
  --module hypertension,diabetes,wellness --with-coverage \
  --out ./samples/cms-connectathon-2026/patients
```

> Note: within the NDJSON export, `subject`/`patient` references use the
> `urn:uuid:` fullUrl form derived from each patient's GPX id (the resolver key
> is the GPX id in `Patient.id`).

---

## 2. Scheduling — SMART Scheduling Links (`$bulk-publish`)

Directory: [`scheduling/`](./scheduling/)

Implements the SMART Scheduling Links bulk-publish flow used to advertise open,
bookable appointment slots to consumer scheduling apps.

| File | Resource | Count | Notes |
| --- | --- | ---: | --- |
| `bulk-publish-manifest.json` | — | — | The document a server returns from `$bulk-publish`; its `output[]` links the NDJSON below. |
| `Location.ndjson` | Location | 40 | Clinic sites across 24 states, with `position` and NPI identifiers. |
| `Schedule.ndjson` | Schedule | 80 | One per (Location × serviceType); `actor` → Location. |
| `Slot.ndjson` | Slot | 14,400 | `free`/`busy`, with SMART booking-deep-link, booking-phone, slot-capacity extensions. |
| `Appointment.ndjson` | Appointment | 2,840 | Booked slots tied to patients from dataset #1 (convenience; not part of SMART Scheduling Links). |

**Service types:** General Practice (`124`) and Immunization (`57`) from the
FHIR `service-type` value set.

**Availability window:** weekdays 2026-07-13 → 2026-08-07, 08:00–17:00 local,
hourly slots. ~20% of slots are `busy` (booked); the rest are `free`.

### Consuming the manifest

The manifest is the entry point. Its `output` array lists each NDJSON file by
type — a client fetches the manifest, then streams each URL:

```bash
curl -s .../scheduling/bulk-publish-manifest.json | jq -r '.output[].url'
```

Referential graph: `Slot.schedule → Schedule`, `Schedule.actor → Location`,
`Appointment.slot → Slot`, `Appointment.participant.actor → Patient/GPX-SYN-…`.

This dataset is produced by the built-in **SMART Scheduling Links** feature
(`atlas publish-scheduling` / `parker_atlas.scheduling`); see
[`docs/smart-scheduling-links.md`](../../docs/smart-scheduling-links.md).

Regenerate (a thin wrapper pinning the connectathon parameters; reads
`patients/Patient.ndjson` for Appointment references):

```bash
python scripts/build_cms_connectathon_scheduling.py
```

Or directly via the CLI:

```bash
atlas publish-scheduling --sites 40 --weeks 4 --slot-minutes 60 --seed 20260712 \
  --service-types general-practice,immunization \
  --window-start 2026-07-13 --patients ./samples/cms-connectathon-2026/patients \
  --out ./samples/cms-connectathon-2026/scheduling
```

---

## Provenance & licensing

Generated with [Apex Atlas](../../README.md) v1.0.0 (Parker Health, Inc.),
Apache-2.0. Population statistics are calibrated to cited public US sources;
scheduling records are structurally synthetic. Not derived from any production
or credentialed clinical dataset.

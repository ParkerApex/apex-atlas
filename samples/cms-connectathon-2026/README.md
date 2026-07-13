# CMS Connectathon 2026 — Synthetic Bulk-Publish Dataset

Synthetic, license-clean FHIR R4 data prepared for the **CMS Connectathon 2026**.
Three independently usable datasets are published here:

1. **Patients** — a 20,000-patient population as FHIR Bulk Data (`$export`)-style NDJSON (relative references).
2. **Scheduling** — open appointment availability as a
   [SMART Scheduling Links](https://github.com/smart-on-fhir/smart-scheduling-links)
   (`$bulk-publish`) dataset, plus booked `Appointment` resources.
3. **Provider directory** — a payer provider directory as a
   [Da Vinci PDEX Plan-Net](http://hl7.org/fhir/us/davinci-pdex-plan-net/) (`$bulk-publish`) dataset.

All records are synthetic. Every resource carries the
`HTEST` ("test health data") `meta.tag`. No record corresponds to a real
individual. See the repository [security & provenance FAQ](../../docs/security-provenance-faq.md).

The whole dataset cross-validates: **246,213/246,213 references resolve across
168,303 resources** — see [`conformance-report.md`](./conformance-report.md),
regenerate with `atlas validate . --refs` / `atlas validate . --ig`.

---

## How to get this data

This dataset lives on **`main`** under
`samples/cms-connectathon-2026/` (≈180 MB total: patients ≈161 MB, scheduling ≈19 MB).

**Option A — clone the repo (main branch):**

```bash
git clone https://github.com/ParkerApex/apex-atlas.git
cd apex-atlas/samples/cms-connectathon-2026
```

**Option B — download individual files** (raw URLs, no clone). Each file is
`https://raw.githubusercontent.com/ParkerApex/apex-atlas/main/samples/cms-connectathon-2026/<path>`, e.g.:

```bash
BASE=https://raw.githubusercontent.com/ParkerApex/apex-atlas/main/samples/cms-connectathon-2026
curl -O $BASE/patients/Patient.ndjson
curl -O $BASE/scheduling/Slot.ndjson
```

**Option C — the SMART Scheduling Links manifest** is self-describing; point a
client at it and follow the `output[]` URLs:

```bash
curl -s https://raw.githubusercontent.com/ParkerApex/apex-atlas/main/samples/cms-connectathon-2026/scheduling/bulk-publish-manifest.json \
  | jq -r '.output[].url'
```

### At a glance

| Dataset | Directory | Files | Rough size |
| --- | --- | --- | ---: |
| Patients (FHIR Bulk Data `$export`) | [`patients/`](./patients/) | 9 NDJSON + metadata | ≈161 MB |
| Scheduling (SMART Scheduling Links `$bulk-publish`) | [`scheduling/`](./scheduling/) | manifest + 4 NDJSON | ≈19 MB |
| Provider directory (Plan-Net `$bulk-publish`) | [`provider-directory/`](./provider-directory/) | manifest + 7 NDJSON | ≈40 KB |

Loading into a FHIR server: the patient NDJSON follows the FHIR
[Bulk Data Access](https://hl7.org/fhir/uv/bulkdata/) layout (one file per
resource type), so most servers can ingest each `*.ndjson` directly. The
scheduling files follow [SMART Scheduling Links](https://github.com/smart-on-fhir/smart-scheduling-links).

---

## 1. Patients — FHIR Bulk Data (`$export`) NDJSON

Directory: [`patients/`](./patients/)

One NDJSON file per resource type, one resource per line — the FHIR
[Bulk Data Access](https://hl7.org/fhir/uv/bulkdata/) convention. Conforms to
US Core 6.1. Patient identity uses the Parker Global Patient Identifier
(`GPX-SYN-…`) under the synthetic namespace.

> **Just want to read a few patients?** The NDJSON files are large. See
> [`patients/examples/`](./patients/examples/) for a handful of complete
> patient records as pretty-printed, human-readable FHIR Bundles (Patient +
> all their linked resources), ranging from a multi-morbid record to a healthy
> one.

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

**Generation parameters:** `seed=2026`, `as-of=2026-07-12`, modules
`hypertension,diabetes,wellness`, `--with-coverage`, US Core 6.1, idiomatic
relative references (`--ref-style relative`).

Regenerate (byte-reproducible with the pinned `--seed` + `--as-of`):

```bash
atlas generate --patients 20000 --seed 2026 --as-of 2026-07-12 --format ndjson \
  --module hypertension,diabetes,wellness --with-coverage --ref-style relative \
  --out ./samples/cms-connectathon-2026/patients
```

> References use idiomatic FHIR Bulk Data relative form (`Patient/GPX-SYN-…`),
> so the export resolves cleanly across files (and against the scheduling
> Appointments) — see the [validation section](#validation--conformance).

---

## 2. Scheduling — SMART Scheduling Links (`$bulk-publish`)

Directory: [`scheduling/`](./scheduling/)

Implements the SMART Scheduling Links bulk-publish flow used to advertise open,
bookable appointment slots to consumer scheduling apps.

> **Just want to read a few?** `Slot.ndjson` is large. See
> [`scheduling/examples/`](./scheduling/examples/) for readable, pretty-printed
> samples — one clinic's Location, Schedules, free/booked Slots, and the
> Appointments booking real patients — plus a single self-contained
> `clinic-availability.example.json` Bundle showing the whole graph.

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

## 3. Provider directory — Da Vinci Plan-Net (`$bulk-publish`)

Directory: [`provider-directory/`](./provider-directory/)

A payer provider directory conforming to the
[Da Vinci PDEX Plan-Net](http://hl7.org/fhir/us/davinci-pdex-plan-net/) IG —
the provider-directory surface referenced by the CMS Interoperability & Patient
Access rule. **25 providers across 21 specialties at 9 facilities.**

> **Want the provider list?** See [`provider-directory/PROVIDERS.md`](./provider-directory/PROVIDERS.md)
> for a readable table of every provider — NPI, name, specialty, NUCC taxonomy,
> setting, and facility — plus the facility list.

| File | Resource | Role |
| --- | --- | --- |
| `bulk-publish-manifest.json` | — | Links the NDJSON via `output[]`. |
| `Organization.ndjson` | Organization | Provider organizations **and** Networks (`type = ntwk`). |
| `Location.ndjson` | Location | Practice sites (address, position, managing org). |
| `Practitioner.ndjson` | Practitioner | Providers with NPI + board qualification (NUCC). |
| `PractitionerRole.ndjson` | PractitionerRole | practitioner ↔ org ↔ location ↔ service ↔ network, with specialty + accepting-new-patients. |
| `HealthcareService.ndjson` | HealthcareService | Services by org at a location. |
| `InsurancePlan.ndjson` | InsurancePlan | Plans referencing their network(s). |
| `Endpoint.ndjson` | Endpoint | A FHIR base URL per org. |

Built from the **same provider roster** that patient encounters draw from, so a
practitioner or facility NPI in a claim (`atlas generate --with-providers`) also
appears here. See [`docs/provider-directory.md`](../../docs/provider-directory.md).

Regenerate:

```bash
atlas publish-provider-directory \
  --base-url https://raw.githubusercontent.com/ParkerApex/apex-atlas/main/samples/cms-connectathon-2026/provider-directory \
  --out ./samples/cms-connectathon-2026/provider-directory
```

---

## Validation & conformance

The whole dataset is referentially consistent and structurally valid. A shipped
report — [`conformance-report.md`](./conformance-report.md) — records the run:
**168,303/168,303 resources structurally valid** (fhir.resources R4B) and
**246,213/246,213 references resolved** (Appointment→Patient bookings included).

Reproduce it:

```bash
# Cross-file referential integrity across all three datasets.
atlas validate ./samples/cms-connectathon-2026 --refs

# Full conformance report (add --validator-jar to include the HL7 FHIR validator).
atlas validate ./samples/cms-connectathon-2026 --ig \
  --ig-report ./samples/cms-connectathon-2026/conformance-report.md
```

---

## Provenance & licensing

Generated with [Apex Atlas](../../README.md) v1.0.0 (Parker Health, Inc.),
Apache-2.0. Population statistics are calibrated to cited public US sources;
scheduling records are structurally synthetic. Not derived from any production
or credentialed clinical dataset.

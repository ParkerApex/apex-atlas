# Integration cookbooks

*Copy-paste recipes for loading Apex Atlas output into production-shaped pipelines.*

Atlas does **not** connect to QHINs, HIEs, Stedi, or CMS Blue Button. These cookbooks show how to **generate** cohorts whose FHIR **maps to** what those channels deliver.

---

## QHIN / TEFCA — clinical summary ingest

**Goal:** Exercise clinical ingestion (Patient → Condition → Encounter → Med → Lab) like network-exchanged US Core data.

```bash
pip install -e ".[dev,data]"

atlas generate --patients 5000 --seed 42 \
  --module hypertension,diabetes,asthma,depression,ckd \
  --with-sdoh --with-providers --with-notes \
  --summary --out ./cohorts/qhin-clinical

# Structural + fidelity
atlas validate ./cohorts/qhin-clinical
atlas validate ./cohorts/qhin-clinical --cohort --module hypertension --min-samples 1000

# Bulk-ingest shape (one NDJSON file per resourceType)
atlas generate --patients 5000 --seed 42 \
  --module hypertension,diabetes,asthma \
  --with-sdoh --with-providers \
  --format ndjson --out ./cohorts/qhin-clinical-ndjson
```

**Expected resource types:** `Patient`, `Condition`, `Observation`, `Encounter`, `MedicationRequest`, `Procedure`, `Practitioner`, `PractitionerRole`, `Location`, `Organization`, `DocumentReference`, SDOHCC `Observation`.

**Ingest tip:** Treat each `GPX-SYN-*.json` bundle as a single patient chart, or load NDJSON by resourceType into your `$import` / warehouse pipeline.

---

## HIE — longitudinal multi-source chart

**Goal:** Multi-condition panels with cross-module progressions and clinical notes — like a queried HIE record.

```bash
atlas generate --patients 2000 --seed 7 \
  --module hypertension,diabetes,heart_failure,ckd,stroke \
  --with-notes --note-types progress,discharge,radiology \
  --with-providers --with-sdoh --summary \
  --out ./cohorts/hie-longitudinal

atlas report ./cohorts/hie-longitudinal \
  --module hypertension,diabetes \
  --out ./cohorts/hie-longitudinal/report.html
```

**What to validate in your pipeline:** condition deduplication, encounter linking, note `DocumentReference.context.encounter`, medication reconciliation across modules.

---

## Stedi — claims, eligibility, and remittance

**Goal:** Payer-shaped FHIR: Coverage, Claim, ExplanationOfBenefit — comparable to clearinghouse / eligibility + claims API workflows.

```bash
atlas generate --patients 3000 --seed 99 \
  --module hypertension,diabetes,wellness,pediatric_wellness \
  --with-coverage --with-claims --with-providers \
  --with-measures --summary \
  --out ./cohorts/stedi-payer

atlas validate ./cohorts/stedi-payer
ls ./cohorts/stedi-payer/MeasureReport-*.json   # population summaries
```

**Expected payer graph:** `Coverage` → `Claim` → `ExplanationOfBenefit`, plus payer `Organization` and `InsurancePlan`. Uninsured patients (sampled from ACS payer mix) receive no claims.

**Ingest tip:** Join Claims to Encounters via shared patient GPX and service dates; EOB `item` lines reference procedure/diagnosis codes from the same synthetic visit.

---

## CMS Blue Button 2.0 — Medicare beneficiary shape

**Goal:** Older-adult chronic panels with Coverage + EOB — without CMS sandbox credentials.

```bash
atlas generate --patients 4000 --seed 20260612 \
  --module hypertension,hypercholesterolemia,heart_failure,diabetes,ckd \
  --with-coverage --with-claims --with-measures \
  --summary --out ./cohorts/blue-button-shaped

# Parquet for analytics / ML feature stores
atlas generate --patients 4000 --seed 20260612 \
  --module hypertension,diabetes,hypercholesterolemia \
  --with-coverage --with-claims \
  --format parquet --out ./cohorts/blue-button-parquet
# → includes parquet-schema.json + generation-metadata.json
```

**Age signal:** Demographics are ACS-sampled; chronic modules fire predominantly in 60+ brackets. Payer mix includes Medicare-weighted rates from `--with-coverage`.

**Not a Blue Button substitute:** Atlas does not call `https://api.bluebutton.cms.gov`. Output is synthetic FHIR with similar resource mix.

---

## Quick validation checklist

| Step | Command |
| --- | --- |
| Schema | `atlas validate ./cohort` |
| Prevalence | `atlas validate ./cohort --cohort --module <name>` |
| Launch set | `atlas validate ./cohort --gtm` |
| Human report | `atlas report ./cohort --module <name> --out report.html` |

See [known-limitations.md](./known-limitations.md) for mirror-vs-copy boundaries and [security-provenance-faq.md](./security-provenance-faq.md) for PHI/licensing questions.

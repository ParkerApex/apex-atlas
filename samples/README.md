# Apex Atlas — sample cohort

A small, ready-to-inspect synthetic cohort so you can see Atlas output without
installing anything. **Synthetic data only — no real patient is depicted.**

## What's here

[`fhir-r4/`](./fhir-r4) — 25 synthetic patients as FHIR R4 **transaction
Bundles** (one `GPX-SYN-*.json` per patient), plus population-level
`MeasureReport-*.json` summaries and a `generation-metadata.json` run manifest.

Each patient bundle is US Core 6.1-conformant and carries the HL7 `HTEST` tag.
Across the cohort you'll find:

| Resource | What it shows |
|---|---|
| Patient | US Core demographics (ACS-sourced), GPX synthetic identifier |
| Condition / Encounter | 10 chronic-disease modules: HTN, diabetes, lipids, depression, asthma, COPD, anxiety, hypothyroidism, osteoarthritis, GERD |
| Observation | vitals + labs, **and** Gravity Project SDOHCC screening responses (`--with-sdoh`) |
| MedicationRequest | first-line therapy, with SDoH-driven adherence gaps |
| DocumentReference | grounded clinical progress notes (`--with-notes`) |
| Coverage / Organization / InsurancePlan | age-stratified payer mix (`--with-coverage`) |
| MeasureReport | DEQM individual + summary, 5 HEDIS-analog measures (`--with-measures`) |

## Reproduce it exactly

Deterministic given the seed:

```bash
atlas generate --patients 25 --seed 4242 \
  --module hypertension,diabetes,hypercholesterolemia,depression,asthma,copd,anxiety,hypothyroidism,osteoarthritis,gerd \
  --with-sdoh --with-coverage --with-measures --with-notes \
  --out samples/fhir-r4

atlas validate samples/fhir-r4          # structural US Core check
```

## Want a bigger / different cohort?

Atlas generates millions of patients across 101 modules and 14 clinical
domains, in FHIR R4/R5, `$export`-aligned NDJSON, or Parquet. See the
[quick start](../README.md#quick-start). Every module's prevalence is checked
against public norms — see the [fidelity scorecard](../docs/fidelity-scorecard.md).

# Ingesting external data

Parker Atlas's runtime loaders read CSVs and YAML files from inside the
package. Real-world data (NHANES, CDC BRFSS, US Census ACS, SEER)
doesn't arrive in that shape. The `atlas ingest` commands bridge that
gap — they consume a clean CSV you prepare (from whatever tooling fits
the data source) plus a small metadata YAML that carries provenance and
tolerance policy, and emit the artifacts the runtime expects.

This document describes the ingestion workflow for the two data axes
currently supported:

1. **Fidelity expectations** (`atlas ingest prevalence`) — age- and
   optionally sex-stratified condition prevalence from NHANES /
   BRFSS / Million Hearts / CDC FastStats.
2. **Demographic distributions** (planned: `atlas ingest demographics`)
   — age × sex / race / ethnicity marginals from US Census ACS.

## Why CSV + metadata

- Every data source has its own native format (XPT, SAS, PUMS CSV, API).
  Parker Atlas doesn't bundle parsers for each; users transform source
  data into Atlas's CSV shape with whatever tooling they prefer
  (Stata, R, Python notebook, SQL query).
- Citations, provenance tier, and tolerance policy belong with the
  numbers but change at a different cadence. They live in a sidecar
  metadata YAML so citation bumps don't require re-running numeric
  extraction.
- Ingest round-trips its output through the runtime loader, so
  malformed metadata fails at ingest time rather than at `atlas
  validate --cohort` time.

## Fidelity expectations — `atlas ingest prevalence`

### Input CSV

One row per (metric, bracket, [sex]) cell. Required columns:

| Column      | Type    | Notes                                                    |
| ----------- | ------- | -------------------------------------------------------- |
| metric_id   | string  | Short identifier; must match a key in `metadata.metrics` |
| bracket     | string  | `LOW-HIGH`, e.g. `18-34`                                 |
| prevalence  | float   | In `[0, 1]`                                              |

Optional columns:

| Column       | Type    | Notes                                                   |
| ------------ | ------- | ------------------------------------------------------- |
| sex          | string  | `female` or `male`. Present → `sex_and_age` strata.     |
| n            | integer | Sample size at the source; informational / audit only.  |
| source_note  | string  | Per-row citation note; not emitted into the expectation.|

If every row for a given `metric_id` has an empty `sex`, Atlas emits an
`age_bracket`-stratified metric. If every row has a non-empty `sex`, it
emits a `sex_and_age` metric. Mixed sex/no-sex rows within a single
metric are rejected.

### Metadata YAML

```yaml
module: hypertension
version: 0.2.0          # bump when numbers change

source:
  name: CDC NCHS + NHANES 2017-2020
  provenance: sourced   # "sourced" or "verified" — ingest refuses "placeholder"
  note: |
    Age-bracketed prevalence from NHANES 2017-2020 pre-pandemic cycle,
    cross-referenced with Million Hearts 2022 estimates.
  citations:
    - source: NHANES 2017-2020 (pre-pandemic) cycle
      url: https://wwwn.cdc.gov/nchs/nhanes/continuousnhanes/default.aspx?Cycle=2017-2020
      version: NHANES 2017-2020
      accessed: "2026-04-23"
      table: "Blood pressure — hypertension prevalence"

tolerance:
  kind: wilson
  confidence: 99

metrics:
  essential_hypertension:
    condition_code: "59621000"
    condition_system: http://snomed.info/sct
```

`provenance` must be `sourced` or `verified` — placeholder expectations
are authored by hand in `src/parker_atlas/validation/expectations/library/`.

### Running

```bash
# Print the rendered expectation YAML to stdout
atlas ingest prevalence \
  -i ./hypertension-targets.csv \
  -m ./hypertension-meta.yaml

# Write directly into the bundled library (requires --overwrite if the
# target file already exists)
atlas ingest prevalence \
  -i ./hypertension-targets.csv \
  -m ./hypertension-meta.yaml \
  -o src/parker_atlas/validation/expectations/library/hypertension.yaml \
  --overwrite

# Then verify the cohort harness still passes:
atlas generate --patients 20000 --seed 42 --module hypertension --out ./cohort
atlas validate ./cohort --cohort --module hypertension
```

### From NHANES microdata to this CSV

A typical workflow a user runs once per dataset refresh:

1. Download the NHANES cycle's blood-pressure datasets
   (BPQ_\*.XPT, BPX_\*.XPT) and demographics (DEMO_\*.XPT) from
   https://wwwn.cdc.gov/nchs/nhanes/.
2. In a notebook, merge by `SEQN`, define hypertension per the cycle's
   criteria, tabulate by age bracket and optionally sex, survey-weight
   using the provided mask and PSU variables.
3. Export the resulting table as a CSV in the format above.
4. Author a small metadata YAML declaring `provenance: sourced` and
   the NHANES cycle as a citation.
5. Run `atlas ingest prevalence` to emit the library file, commit both
   the CSV and the generated YAML so the provenance trail is auditable
   from source CSV to runtime artifact.

## Demographic distributions (planned)

`atlas ingest demographics` will accept an ACS-shaped CSV (joint age ×
sex × race distributions) and write
`src/parker_atlas/references/tables/age_sex.csv`,
`…/race.csv`, and `…/ethnicity.csv` with a provenance sidecar. Tracked
as follow-up work.

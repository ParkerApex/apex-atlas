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

## Demographic distributions — `atlas ingest demographics`

Companion to the prevalence pipeline, for the demographic reference
CSVs in `src/parker_atlas/references/tables/`. Writes two files side by
side: the validated CSV at `--output`, and a `<basename>.provenance.yaml`
sidecar with the citation chain.

### Input CSV (three shapes)

| `table`     | Required columns                               |
| ----------- | ---------------------------------------------- |
| `age_sex`   | `age_low, age_high, sex, weight`               |
| `race`      | `code, display, weight`                        |
| `ethnicity` | `code, display, weight`                        |

`sex` must be `female` or `male`. `age_low <= age_high`, both
non-negative integers. `weight` must be a positive number; the sampler
normalizes rows so weights don't need to sum to 1.

### Metadata YAML

```yaml
table: age_sex           # age_sex | race | ethnicity
version: 0.2.0

source:
  name: US Census ACS 2023 1-year estimates
  provenance: sourced    # or verified; ingest refuses placeholder
  url: https://api.census.gov/data/2023/acs/acs1
  citations:
    - source: American Community Survey 2023 (1-year estimates)
      url: https://api.census.gov/data/2023/acs/acs1
      version: ACS 2023
      accessed: "2026-04-23"
      table: "B01001 — Sex by age"
```

### Running

```bash
atlas ingest demographics \
  -i ./age_sex.csv \
  -m ./age_sex_meta.yaml \
  -o src/parker_atlas/references/tables/age_sex.csv \
  --overwrite
# Writes:
#   src/parker_atlas/references/tables/age_sex.csv
#   src/parker_atlas/references/tables/age_sex.provenance.yaml
```

Repeat for `race` and `ethnicity` with their own CSV + metadata pairs.

### Source → CSV transformation

ACS publishes microdata (PUMS) and aggregate tables (the Census Data
API). A typical workflow:

1. Query `api.census.gov/data/2023/acs/acs1?get=...` for the joint
   age × sex population estimates in table `B01001`.
2. Pivot the API response into the `age_low, age_high, sex, weight`
   shape (weights are raw population counts or proportions; either
   works — the sampler normalizes).
3. Write a small metadata YAML carrying the ACS release year and
   table identifier.
4. Run `atlas ingest demographics`.

For race/ethnicity, tables `B02001` and `B03003` respectively.

## Progression rates — `atlas ingest progression`

Sources the `(after_years, probability)` rate of a one-hop progression
declared in a clinical module. Output is a `<module>.progressions.yaml`
overlay file that the runtime loader applies on top of the module YAML
at load time, overriding the inline rate.

The overlay can only **override existing** progressions — it cannot
add new ones. Adding a progression target requires a module YAML edit
(the target condition must exist as a sibling). This split keeps the
structural shape of the module hand-authored and the *rates* sourced.

### Input CSV

| Column        | Required | Notes                                              |
| ------------- | -------- | -------------------------------------------------- |
| `from`        | yes      | spec_id of the source condition (must exist)       |
| `to`          | yes      | spec_id of the target condition (must exist)       |
| `after_years` | yes      | integer ≥ 0                                        |
| `probability` | yes      | float in [0, 1]                                    |
| `source_note` | no       | free text for audit; ignored by the runtime        |

### Metadata YAML

```yaml
module: hypertension
version: 1.0.0
source:
  name: KDIGO 2024 CKD Guideline + USRDS 2023 ADR
  provenance: sourced       # or verified; ingest refuses placeholder
  url: https://kdigo.org/guidelines/ckd-evaluation-and-management/
  citations:
    - source: Hsu CY et al. Arch Intern Med 2005
      url: https://jamanetwork.com/journals/jamainternalmedicine/fullarticle/486521
      accessed: "2026-04-25"
```

### Running

```bash
atlas ingest progression \
  -i ./hypertension.csv \
  -m ./hypertension_meta.yaml \
  -o src/parker_atlas/modules/library/hypertension.progressions.yaml
```

The output is round-tripped through `apply_progressions_overlay`
against the matching bundled module before being written, so unknown
`(from, to)` pairs and bad rate values fail at ingest time.

### Authoring workflow

1. Identify the source/target condition spec_ids in the module YAML.
2. Pick a defensible rate from the literature (KDIGO, USRDS, cohort
   studies). Document the citation chain in the metadata YAML.
3. Run `atlas ingest progression`.
4. Re-run the cohort harness (`atlas validate --cohort --module NAME`)
   to confirm the new rate stays inside the existing tolerance, or
   adjust the bundled expectation target if it has shifted materially.
5. Commit the input CSV, metadata, and generated overlay so the
   provenance chain is auditable from source row to runtime artifact.

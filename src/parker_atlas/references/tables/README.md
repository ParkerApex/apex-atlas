# Reference distributions

These CSV files are the **source of truth** for demographic sampling
distributions. The loader in `parker_atlas/references/__init__.py` reads
them at first use and caches the result.

## Provenance

Each CSV has a sibling `<name>.provenance.yaml` carrying the citation
chain for its numbers. Three provenance tiers mirror the fidelity-
expectation system:

- `placeholder` — curated approximations; not sourced from a public
  dataset.
- `sourced` — targets drawn from the listed public citations, but not
  independently re-verified by the project.
- `verified` — numbers re-computed from public microdata by the project
  and matched against the citation within tolerance.

Current status:

| File              | Provenance | Source                                                                    |
| ----------------- | ---------- | ------------------------------------------------------------------------- |
| `age_sex.csv`     | sourced    | US Census Bureau Vintage 2024 annual estimates (NC-EST2024-SYASEXN)       |
| `race.csv`        | sourced    | US Census 2020 Decennial Census — Race Alone populations                  |
| `ethnicity.csv`   | sourced    | US Census Bureau Vintage 2024 (Hispanic/Latino share)                     |
| `names.csv`       | placeholder| Curated common US names; not drawn from Census name frequencies           |

Regenerate any of these via `atlas ingest demographics --input X.csv
--metadata X_meta.yaml --output src/parker_atlas/references/tables/X.csv
--overwrite`. See `docs/ingestion.md` for the full workflow, including
the ACS → CSV transformation path.

## Files

| File             | Schema                                                                   |
| ---------------- | ------------------------------------------------------------------------ |
| `age_sex.csv`    | `age_low, age_high, sex, weight` — joint age-bracket × sex distribution  |
| `race.csv`       | `code, display, weight` — OMB race codes with population weight          |
| `ethnicity.csv`  | `code, display, weight` — OMB ethnicity codes with population weight     |
| `names.csv`      | `pool, name` — three pools: `first_female`, `first_male`, `last`         |

Weights do not need to sum to exactly 1.0 — the sampler normalizes them.

## Adding a new distribution

1. Create the CSV in this directory.
2. Add a loader in `parker_atlas/references/__init__.py`.
3. Document the schema here.
4. Update tests.
5. If the data is externally sourced, accompany the CSV with a
   `<name>.provenance.yaml` via `atlas ingest demographics`.

## Known caveats

- The `age_sex.csv` brackets (0-17, 18-39, 40-59, 60-99) are chosen to
  match the NHANES age stratification used by the hypertension fidelity
  expectation, not ACS's usual (18-44, 45-64, 65+). Single-year Census
  estimates are aggregated up to these brackets at ingest time.
- The `race.csv` "Other Race" row aggregates the Census 2020 "Some
  other race alone" and "Two or more races" categories, because the
  OMB-code enum in `parker_atlas.core.demographics.Race` does not
  separately track a multiracial category. Splitting those out is a
  future enhancement tied to enum expansion.
- `names.csv` is still placeholder; Census name-frequency ingestion is
  deferred until (if) Atlas starts generating names in a more principled
  way. Hand-editing this file is the current workflow.

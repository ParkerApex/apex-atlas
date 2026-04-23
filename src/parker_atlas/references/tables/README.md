# Reference distributions

These CSV files are the **source of truth** for demographic sampling
distributions. The loader in `parker_atlas/references/__init__.py` reads
them at first use and caches the result.

## Current state

**All files in this directory are curated placeholder distributions, not
yet sourced from US Census ACS or any other public dataset.** They are
shaped to be roughly consistent with US population marginals so that
synthetic output looks plausible, but they **must not be cited as
ACS-derived** or used for statistical fidelity claims.

Replacing these with ACS-backed samples is tracked under Milestone 1
follow-up work (see `docs/roadmap.md`). That will involve:

- Sourcing ACS 5-year PUMS microdata (public domain)
- Tabulating joint distributions at appropriate granularity
- Preserving provenance metadata (release year, query date, citation)
- Adding a provenance manifest so `atlas status` can show the active
  reference-data version

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

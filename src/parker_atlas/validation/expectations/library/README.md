# Fidelity expectations

Each YAML file in this directory declares **fidelity targets** that the
cohort-validation harness uses to check generated output. One file per
module. Filename must match the module name (e.g. `hypertension.yaml`
for the `hypertension` module).

## Status

All bundled expectations are **curated placeholders**. They currently
mirror the prevalence declared in the corresponding module YAML, so the
harness catches pipeline bugs but not calibration drift. Externally-cited
expectations (NHANES, CDC BRFSS, SEER) will land as those datasets are
ingested — at which point the expectation file diverges from the module's
own rates and the harness begins testing calibration too.

## Schema

```yaml
module: <string>          # Must match a bundled module name
version: <semver>
source:
  name: <string>          # Data provenance label
  url: <string>           # (optional) citation URL
  note: <string>          # (optional) notes on sourcing / scope

metrics:
  - id: <short identifier>
    kind: conditional_prevalence   # Only kind supported today
    condition_code: <terminology code>
    condition_system: <terminology system URL>
    stratify_by: age_bracket       # Only stratification supported today
    tolerance:
      kind: absolute | normal | wilson
      value: <float>               # required only for kind=absolute
      confidence: 90 | 95 | 99 | 99.9   # optional, default 95; normal/wilson only
    targets:
      "<LOW>-<HIGH>": <float>      # Prevalence rate in [0, 1]
      ...
```

### Tolerance kinds

| Kind       | Check                                                                                                  | When to use                                               |
| ---------- | ------------------------------------------------------------------------------------------------------ | --------------------------------------------------------- |
| `absolute` | `\|actual - target\| <= value`                                                                         | Simple, coarse; ignores sampling variance.                |
| `normal`   | Two-sided z-test under H0: true prop = target. Half-width = `z * sqrt(target*(1-target)/n)`.           | Principled for proportions well away from 0 or 1.         |
| `wilson`   | Wilson score CI *around the observed* proportion; passes if target is inside.                          | Robust at extreme p (near 0 or 1). Preferred modern default. |

`z` is chosen from `confidence`:
- 90% → 1.6449
- 95% → 1.9600   (default)
- 99% → 2.5758
- 99.9% → 3.2905

## Adding an expectation

1. Create `<module>.yaml` here.
2. Document the source in the `source:` block.
3. Pick a tolerance that is defensible given sampling variance at the
   cohort sizes you expect to run.
4. Run `atlas validate <out> --cohort --module <name>` against a
   sufficiently large cohort to verify the expectation is met.
5. If using external sources, link to the authoritative publication or
   data release.

## Tolerance selection

Prefer `wilson` 95% as the default. Wilson-score CIs are well-behaved
across the full [0, 1] range — including observed proportions near 0
or 1, where `normal` degenerates and `absolute` is either too tight
or too loose.

### False-positive rate under CI tolerance

A CI-based tolerance at confidence `c%` has, by construction, a per-metric
false-failure rate of `(100 - c)%`. For 95% CIs that's ~5% per bracket per
run; a 5-bracket expectation has ~23% chance of flagging at least one
false positive in any given cohort. Mitigations:

- Run with larger cohorts so CIs are narrow relative to any *real* drift.
- Raise `confidence` to 99% or 99.9% if you want tighter gating without
  changing cohort size.
- Run the harness over multiple seeds in CI and require a majority to
  pass (not yet supported by the CLI — pending feature).

### Choosing `min_samples`

At cohort size N with a bracket holding `f * N` patients, the
~95% Wilson half-width around observed proportion `p` is roughly
`1.96 * sqrt(p*(1-p)/(f*N))`. Under `--min-samples`, brackets with
fewer than the threshold patients are skipped with a notice rather
than evaluated on too-noisy data.

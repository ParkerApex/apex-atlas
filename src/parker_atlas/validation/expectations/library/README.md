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
      kind: absolute               # Only tolerance kind supported today
      value: <float>               # e.g. 0.05 = ±5 percentage points
    targets:
      "<LOW>-<HIGH>": <float>      # Prevalence rate in [0, 1]
      ...
```

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

`absolute` tolerance compares `|actual - target| ≤ value`. It is simple
but ignores sampling variance — pick generous tolerances until the
harness grows confidence-interval-aware comparisons. A rough rule for
Bernoulli rates at cohort size N:

```
2 * sqrt(p * (1 - p) / N)
```

is the ~95% normal CI half-width for a proportion. Tolerances should
comfortably exceed that at the cohort sizes you run, or you'll get
false failures on small brackets. The harness also respects
`--min-samples` and skips brackets with too few patients.

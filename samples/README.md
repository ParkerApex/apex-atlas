# Apex Atlas — sample cohorts

**Synthetic data only — no real patient is depicted.**

## Bundled preview (25 patients)

[`fhir-r4/`](./fhir-r4) — inspect in GitHub without installing Atlas. One US Core 6.1
transaction Bundle per patient (`GPX-SYN-*.json`), DEQM MeasureReports, and
`generation-metadata.json`.

```bash
atlas validate samples/fhir-r4
```

## Launch-demo cohorts (10k / 100k / 1M)

Full-scale samples are **built locally** and published as release assets — not
checked into git (multi-GB at 100k+).

```bash
# 10k launch-demo (rich cohort: notes, SDoH, coverage, claims, providers, measures)
./scripts/build_sample_cohorts.sh 10000 20260612

# Package for GitHub Release
tar -czf launch-demo-10000-patients.tar.gz -C samples launch-demo-10000-patients
```

Each built cohort includes:

| Artifact | Purpose |
| --- | --- |
| `GPX-SYN-*.json` | One FHIR R4 bundle per patient |
| `MeasureReport-*.json` | Population-level quality summaries |
| `generation-metadata.json` | Seed, modules, feature flags (audit trail) |
| `cohort-report.html` | Demographics + fidelity snapshot |
| `LIMITATIONS.md` | Mirror-vs-copy boundaries |

**Validation at scale:** structural check always runs; full `atlas validate --gtm`
runs automatically only for cohorts ≤500 patients. For 10k+, headline module
fidelity checks run on hypertension and diabetes; see the
[fidelity scorecard](../docs/fidelity-scorecard.md) for per-module coverage.

## Integration cookbooks

Generate production-mappable FHIR for QHIN, HIE, Stedi, and CMS Blue Button-shaped
workflows: [`docs/integration-cookbooks.md`](../docs/integration-cookbooks.md).

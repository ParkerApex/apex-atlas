# Apex Atlas — Known Limitations

*Last updated: 2026-06-12*

This page distinguishes what Apex Atlas **sources**, **validates**, **simulates**, and **defers**. Use it when evaluating fitness for research, integration testing, AI training, or commercial deployment.

## What Atlas is

- **Fully synthetic** — no real patients, no credentialed datasets (MIMIC, UK Biobank, etc.), no ingestion from QHIN, HIE, Stedi, or CMS Blue Button production feeds.
- **Mirrors real-world care statistically** — prevalence, comorbidity chains, utilization (including SDoH-driven gaps), payer mix, and measure numerators calibrated to public US epidemiology — not arbitrary FHIR fixtures.
- **Maps to production FHIR channels** — output uses the same resource types and profiles your pipelines consume from QHIN/TEFCA exchange, HIE query/response, payer claims APIs, and Medicare Blue Button-style FHIR.
- **Publicly sourced** — rates trace to CDC, NHANES, ACS, SEER, AHA, ACOG, BRFSS, and peer-reviewed literature cited per module.
- **FHIR-first** — R4/R5 bundles, US Core 6.1 builders, Gravity SDOHCC, DEQM MeasureReport (first cut).
- **Validation-oriented** — cohort fidelity harness compares aggregate output to cited targets; see the [fidelity scorecard](./fidelity-scorecard.md).

### Mirror vs. copy

| | Atlas | Production (QHIN / HIE / payer FHIR) |
| --- | --- | --- |
| **Individual patients** | Synthetic GPX-SYN identifiers | Real individuals (PHI) |
| **Population distributions** | Matched to cited public targets | Empirical from live data |
| **Resource graph** | Patient → Condition → Encounter → Med → Claim/EOB | Same FHIR shapes |
| **Provenance** | `generation-metadata.json` + module `cites:` | Source organization / TEFCA participant |

Atlas helps you test **downstream logic** (risk models, prior auth, care gaps, measure extraction, chart summarization) against panels that behave like real populations — without access to those networks during early build.

## Capability tiers

| Tier | Meaning | Marketing use |
| --- | --- | --- |
| **Tier 1** | Citations + sourced fidelity expectations + cohort validation + clinical review | Headline claims, sample cohorts, `atlas validate --gtm` |
| **Tier 2** | Citations + representative FHIR emits + smoke tests + sourced expectations (cohort-validated) | Bundled library; cite module name, not “clinically validated” |
| **Tier 3** | Experimental (`atlas author` drafts pending licensed sign-off) | Community preview only |

See the [module catalog](./module-catalog.md) for per-module tier and review status.

## Validated today

- **Structural FHIR** — schema + US Core Patient/Condition minimums via `atlas validate`.
- **Cohort fidelity** — per-module expectations vs. Wilson-interval tolerance via `atlas validate --cohort`.
- **SDoH causal signal** — encounter and medication adherence modifiers; see [SDoH benchmark](./sdoh-causal-benchmark.md).
- **Deterministic generation** — fixed seed → reproducible cohort (except LLM-authored note prose across model versions).

## Not validated / incomplete

| Area | Status | Notes |
| --- | --- | --- |
| **Clinical realism (individual patient)** | Not claimed | Aggregate rates match public norms; individual charts are plausible, not audited chart-by-chart. |
| **Licensed clinician sign-off** | In progress | CLI `SIGNOFF.md` gate exists; web review UI available at [clinical-review.html](./clinical-review.html). Most modules are internally reviewed, not externally signed. |
| **US Core DocumentReference 6.1** | Partial | Notes are base FHIR DocumentReference, not full US Core profile (missing author, identifier slices). |
| **IPS 2.0 conformance** | Post-v1 | International Patient Summary not implemented. |
| **SMART on FHIR / production Bulk $export** | Dev first cut | `atlas serve` exposes async `$export` for demos; no OAuth, no multi-tenant SLA. |
| **Claims & EOB** | First cut | One Claim + EOB per covered Encounter; not payer-specific editing or remittance logic. |
| **Quality measures** | HEDIS-analog (5) | Not NCQA-certified; DEQM-profiled MeasureReports for testing only. |
| **Clinical notes — blinded audit** | Not run | Template + LLM progress notes ship; discharge and radiology notes are template-first; no published ≥80% clinician acceptance study. |
| **Structured ↔ unstructured consistency check** | Planned | No automated contradiction detector between FHIR resources and note text yet. |
| **Longitudinal multi-year drift** | Post-v1 | Single simulated timeline per patient; no policy counterfactuals. |
| **Genomics / imaging pixels** | Post-v1 | Procedures reference imaging; no DICOM or genomic variants. |
| **International locales** | US-only | ACS demographics, US Core, US epidemiology sources. |

## Statistical caveats

- Fidelity checks are **aggregate** at declared strata (age/sex brackets). Small cohorts widen confidence intervals.
- The [scorecard](./fidelity-scorecard.md) is a single-seed snapshot (N=8,000 per module). Occasional single-stratum breaches at ~99% confidence are expected from multiple comparisons.
- Cross-module progressions can affect multi-module cohorts; single-module validation isolates each module in the scorecard.

## LLM features

- **`--notes-strategy llm`** and **`atlas author research`** call external APIs (Anthropic by default; OpenAI optional). Requires your API key; not used for core deterministic generation.
- LLM note prose may vary across model versions even at temperature 0.
- Authoring drafts require clinician promotion before library merge.

## Terminology & licensing

- SNOMED CT, LOINC, RxNorm, and ICD-10-CM codes appear in output. **UMLS Affiliate License** covers typical US research and integration testing; international deployment requires separate assessment.
- Atlas does not redistribute UMLS release files; codes are embedded in module YAML only.

## When not to use Atlas

- Substituting for real-world evidence or regulatory submission datasets.
- Re-identification research (synthetic ≠ anonymous if combined with external keys).
- Production clinical decision support without independent validation.
- Non-US markets without swapping demographics, profiles, and terminology policy.

## Reporting gaps

Open a [GitHub issue](https://github.com/ParkerApex/apex-atlas/issues) or email [atlas@parkerapex.com](mailto:atlas@parkerapex.com). Security issues: [security@parkerapex.com](mailto:security@parkerapex.com).

# Apex Atlas GTM Readiness

*Last updated: 2026-05-22*

This document converts the roadmap into the practical work needed to make Apex Atlas credible in public, useful in sales conversations, and safe to put in front of enterprise healthcare buyers.

## Positioning

**Apex Atlas is the synthetic FHIR data layer for healthcare AI and interoperability teams that need cohorts mirroring real US care patterns — not just profile-conformant fixtures — without PHI or credentialed dataset delays.**

The GTM message should stay concrete:

- Generate FHIR-native patient populations with GPX identifiers that **map to production ingestion paths** (QHIN/TEFCA, HIE, payer FHIR, Bulk `$export`).
- Mirror common clinical, payer, SDoH, pediatric, maternal, and quality-measure **distributions** sourced from public epidemiology.
- Trace rates to public sources and validate cohort output against those targets.
- Produce records useful for **AI training, end-to-end integration testing, demo environments, and quality reporting pipelines** — not schema-only conformance checks.

Avoid overclaiming clinical validation. The strongest accurate claim is that Atlas is publicly sourced, auditable, FHIR-first, and validation-oriented.

## Prime-Time Definition

Apex Atlas is prime-time when a prospect can do three things without Parker engineering in the room:

1. Install the package and generate a useful cohort in under 15 minutes.
2. Understand what is synthetic, what is sourced, what is validated, and what is still experimental.
3. Evaluate a realistic sample population, validation scorecard, and commercial offer.

## Release Assets

| Asset | Owner | Status | Exit bar |
| --- | --- | --- | --- |
| README quick start | Product/Engineering | ✅ v1 | Install, generate, validate, inspect modules |
| Module catalog | Clinical/Engineering | ✅ | 101-module table with tier, fidelity, review status |
| Validation scorecard | Engineering/Clinical | ✅ | [fidelity-scorecard.md](./fidelity-scorecard.md) — 100 modules |
| Sample cohorts | Engineering | Script ready | `scripts/build_sample_cohorts.sh` — run locally for 10k/100k/1M |
| Demo scripts | GTM/Product | ✅ | `scripts/demo_ai_training.sh`, `demo_fhir_integration.sh`, `demo_quality_measures.sh` |
| Commercial one-pager | GTM/Legal | ✅ | [commercial-one-pager.md](./commercial-one-pager.md) |
| Security and data provenance FAQ | Legal/Clinical | ✅ | [security-provenance-faq.md](./security-provenance-faq.md) |
| Known limitations | Product/Clinical | ✅ | [known-limitations.md](./known-limitations.md) |
| Clinical review UI | Clinical | ✅ | [clinical-review.html](./clinical-review.html) |
| Launch announcement | Founder/GTM | Needed | Publishable post tied to release tag |

## Buyer Motions

| Buyer | Primary pain | Demo path |
| --- | --- | --- |
| Healthcare AI startups | Need realistic training/evaluation data without PHI friction | Generate chronic + notes cohort, show structured/unstructured consistency |
| Health system integration teams | Need realistic FHIR test panels matching HIE/QHIN ingestion | Generate US Core bundles + NDJSON; show same resource graph as exchanged clinical data |
| Payers, clearinghouses, and API vendors | Need claims, eligibility, and remittance test data | Generate Coverage, Claim, EOB cohorts (`--with-coverage --with-claims`); comparable to Stedi-style workflows |
| Payers and quality vendors | Need measure and HEDIS-analog test data | Generate `--with-measures` cohort with DEQM MeasureReport + claims-like resources |
| Medicare / Blue Button integrators | Need beneficiary-shaped FHIR without CMS sandbox limits | Age-stratified payer mix, Coverage + EOB, chronic-care modules |
| Academic researchers | Need license-clean synthetic datasets | Show citations, metadata, validation scorecard, reproducible seeds |
| Platform teams | Need embedded synthetic data infrastructure | Show CLI, module DSL, provenance, Parquet, and commercial support path |

## 100-Module Launch Rule

The launch target is 100 modules, but the GTM promise should be quality-weighted:

- **Tier 1:** top launch modules with sourced fidelity expectations and tests.
- **Tier 2:** modules with citations, realistic emits, and smoke tests.
- **Tier 3:** experimental modules that are clearly labeled and excluded from headline claims.

Do not market a raw module count without the tiering. The count gets attention; the tiering earns trust.

## GTM Workplan

| Phase | Goal | Deliverables |
| --- | --- | --- |
| RC0 | Make the repo self-explanatory | README polish, roadmap, GTM doc, architecture consistency, install verification |
| RC1 | Prove module scale | 100-module catalog, generation smoke tests, source coverage table |
| RC2 | Prove fidelity | Expectations for Tier 1 modules, cohort validation reports, known-limitations page |
| RC3 | Prove buyer value | Sample cohorts, demos, commercial one-pager, launch site/docs |
| v1.0 | Public launch | Signed release, PyPI package, release notes, validation scorecards, announcement |

## Launch Gates

- 100 modules load through `atlas modules`.
- All modules have `cites:` metadata and pass module smoke tests.
- Tier 1 modules have sourced fidelity expectations and pass cohort validation at documented cohort sizes.
- `atlas launch-demo` generates a rich demo cohort with notes, SDoH, coverage, claims, providers, and MeasureReports.
- `atlas validate --gtm` runs structural validation plus the launch-hardened sourced expectation set.
- `atlas generate`, `atlas validate`, `atlas validate --cohort`, `atlas report`, NDJSON, and Parquet paths are tested in CI.
- Sample cohorts include `generation-metadata.json`, validation scorecards, and a plain-language limitations file.
- README, roadmap, architecture, ingestion, licensing, commercial, and contribution docs agree on counts and claims.
- Package can be installed from a clean environment with documented extras.
- Commercial inquiry path is visible and legally aligned with `COMMERCIAL.md`.

## Known GTM Risks

| Risk | Response |
| --- | --- |
| Module count grows faster than validation coverage | Tier modules visibly and reserve strongest claims for Tier 1 |
| Prospects read "synthetic" as "clinically validated" | Use precise language: sourced, auditable, validation-oriented, not real-patient-derived |
| Enterprise buyers ask for indemnity, SLAs, or custom modules | Route to commercial license and services |
| FHIR conformance claims are challenged | Publish validator versions, profiles, sample bundles, and known gaps |
| LLM-authored notes raise data provenance questions | Emphasize opt-in runtime generation, synthetic structured grounding, and no PHI training dependency |

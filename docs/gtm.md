# Apex Atlas GTM Readiness

*Last updated: 2026-05-22*

This document converts the roadmap into the practical work needed to make Apex Atlas credible in public, useful in sales conversations, and safe to put in front of enterprise healthcare buyers.

## Positioning

**Apex Atlas is the synthetic FHIR data layer for healthcare AI and interoperability teams that need realistic, license-clean patient populations without waiting on restricted real-world datasets.**

The GTM message should stay concrete:

- Generate FHIR-native patient populations with GPX identifiers.
- Cover common clinical, payer, SDoH, pediatric, maternal, and quality-measure workflows.
- Trace rates to public sources and validate cohort output against those targets.
- Produce records that are useful for AI training, FHIR integration testing, demo environments, and quality reporting pipelines.

Avoid overclaiming clinical validation. The strongest accurate claim is that Atlas is publicly sourced, auditable, FHIR-first, and validation-oriented.

## Prime-Time Definition

Apex Atlas is prime-time when a prospect can do three things without Parker engineering in the room:

1. Install the package and generate a useful cohort in under 15 minutes.
2. Understand what is synthetic, what is sourced, what is validated, and what is still experimental.
3. Evaluate a realistic sample population, validation scorecard, and commercial offer.

## Release Assets

| Asset | Owner | Status | Exit bar |
| --- | --- | --- | --- |
| README quick start | Product/Engineering | Strong, needs v1 polish | A new developer can install, generate, validate, and inspect modules without asking for help |
| Module catalog | Clinical/Engineering | Started | 100-module table with domain, source status, fidelity status, and reviewer status |
| Validation scorecard | Engineering/Clinical | Partial | Published scorecard for at least the launch sample cohorts |
| Sample cohorts | Engineering | Needed | 10k, 100k, and 1M patient downloads with metadata and validation reports |
| Demo scripts | GTM/Product | Needed | Three repeatable scripts: AI training, FHIR integration, quality measures |
| Commercial one-pager | GTM/Legal | Needed | Clear boundary between Apache 2.0 use and commercial support/license |
| Security and data provenance FAQ | Legal/Clinical | Needed | Answers PHI, MIMIC/UK Biobank, licensing, UMLS, and re-identification questions |
| Launch announcement | Founder/GTM | Needed | Publishable post tied to a release tag and validation artifacts |

## Buyer Motions

| Buyer | Primary pain | Demo path |
| --- | --- | --- |
| Healthcare AI startups | Need realistic training/evaluation data without PHI friction | Generate chronic + notes cohort, show structured/unstructured consistency |
| Health system integration teams | Need realistic FHIR test panels | Generate US Core Bundle + NDJSON output with providers, coverage, SDoH |
| Payers and quality vendors | Need measure and claims-like test data | Generate quality-measure cohort with Coverage, Claim, EOB, MeasureReport |
| Academic researchers | Need license-clean synthetic datasets | Show citations, metadata, validation scorecard, reproducible seeds |
| Platform teams | Need embedded synthetic data infrastructure | Show CLI, module DSL, provenance, Parquet, and commercial support path |

## 100-Module Launch Rule

The launch target is 100+ modules, but the GTM promise should be quality-weighted:

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

- 100+ modules load through `atlas modules`.
- All modules have `cites:` metadata and pass module smoke tests.
- Tier 1 modules have sourced fidelity expectations and pass cohort validation at documented cohort sizes.
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

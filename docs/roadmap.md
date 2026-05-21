# APEX Atlas Roadmap

This roadmap describes the path from initial scaffold to public v1.0 release. Dates are indicative; actual delivery depends on team capacity and clinical reviewer availability.

## Milestone 0 — Scaffold (complete)

- Repository structure and packaging
- Dual-license agreement and CLA
- Parker GPX Identifier implementation with test suite
- Architecture documentation
- Contribution guide

## Milestone 1 — Core Generator (Weeks 1–6)

**Goal:** generate minimally realistic demographic patient populations with GPX identifiers, valid FHIR output, no clinical events yet.

- Patient lifecycle object with birth, death, and timeline
- Discrete-event scheduler
- Demographic sampling from US Census ACS (age, sex, race, ethnicity, geography)
- SDoH sampling from CDC SVI and BRFSS (insurance, housing, education, income)
- FHIR R4 Patient resource with US Core 6.1 conformance
- FHIR Bundle output, NDJSON output
- CLI scaffolding (`atlas generate`, `atlas validate`)
- Generate 1M synthetic patients in under 10 minutes on a single host

**Exit criteria:** 1M-patient generation passes US Core 6.1 validation, demographic distributions match ACS within 2% across all marginals.

## Milestone 2 — First 10 Clinical Modules (Weeks 7–12)

**Goal:** prove the module DSL and runtime by hand-authoring the ten highest-prevalence chronic conditions.

- Module DSL specification and YAML parser
- State machine runtime
- Encounter, Condition, Observation, MedicationRequest FHIR builders
- SNOMED CT, LOINC, RxNorm terminology services (offline snapshots)
- First 10 modules: hypertension, type 2 diabetes, hyperlipidemia, asthma, COPD, depression, anxiety, obesity, CHF, atrial fibrillation
- Statistical validation harness v1

**Exit criteria:** all 10 modules' disease prevalence in synthetic output matches CDC/NHANES published rates within declared tolerance.

## Milestone 3 — LLM-Assisted Authoring (Weeks 13–18)

**Goal:** enable 10x faster module authorship through LLM assistance.

- Natural-language-to-DSL scaffolding pipeline
- Epidemiology citation retrieval
- Automated validation loop (author → generate → compare → iterate)
- Clinician review UI (web-based)
- LLM provider abstraction (Anthropic, OpenAI, local models)
- Second batch of 40 modules authored via the pipeline

**Exit criteria:** 50 total modules in the library, at least 30 authored via the LLM pipeline.

## Milestone 4 — Clinical Notes (Weeks 19–24)

**Goal:** generate internally-consistent unstructured clinical notes grounded in the structured patient record.

- Note grounding layer (structured data → prompt context)
- Note generators: H&P, progress note, discharge summary, radiology report
- Style matching from public exemplar corpora (MT Samples)
- Note-to-structured consistency validation
- DocumentReference FHIR resource integration

**Exit criteria:** generated notes pass an independent clinician-reviewed fidelity audit with 80%+ acceptance rate.

## Milestone 5 — v1.0 Public Release (Weeks 25–26)

**Goal:** ship v1.0 as a signed, validated release.

- 100+ modules in the library
- Full US Core 6.1 and IPS conformance
- Bulk Data Access ($export) support
- Parquet output format
- Sample populations (1M, 10M, 100M) hosted for download
- Publication of validation scorecard
- Dual-license go-live: PyPI package, GitHub release, commercial tier open
- Launch announcement timed to an industry event (HIMSS, FHIR DevDays)

**Exit criteria:** 1,000 GitHub stars within 30 days of launch, three signed enterprise licensing agreements, two academic citations in progress.

## Post-v1 directions

- Genomic and family history generation
- Medical imaging reference integration (synthetic DICOM)
- Longitudinal drift and population simulation (epidemics, policy changes)
- International locales and non-US profile conformance
- Federation: multiple Atlas instances sharing module libraries

## Dependencies and risks

- **Clinical reviewer capacity** is the binding constraint, not engineering. Every module requires a licensed clinician sign-off.
- **Terminology licensing** is straightforward in the US (UMLS Affiliate License covers SNOMED CT, LOINC, RxNorm, ICD-10) but varies internationally.
- **LLM provider stability** — we maintain at least two provider backends so that provider-specific changes do not block authoring.

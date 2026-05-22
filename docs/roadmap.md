# APEX Atlas Roadmap

*Last updated: 2026-05-22 — Vincent J. Lopez, Founder & CEO, Parker Health, Inc.*

Dates are indicative; actual delivery depends on team capacity and clinical reviewer availability. This document reflects current delivery state as of the last-updated date above.

---

## Milestone 0 — Scaffold ✅ Complete

- Repository structure, packaging, and dual-license framework (Apache 2.0 + commercial)
- CLA and contribution governance
- Parker GPX Identifier implementation with full test suite
- Architecture documentation and contribution guide

---

## Milestone 1 — Core Generator ✅ Complete

**Goal:** Generate realistic synthetic patient populations with GPX identifiers, valid FHIR output, demographic sampling, and foundational clinical infrastructure.

**Delivered:**

- Patient lifecycle with birth, age computation, and simulated-date timeline
- Demographic sampling from US Census ACS 2024 1-year estimates (age/sex/race/ethnicity)
- FHIR R4 US Core 6.1 Patient resource with race/ethnicity/birthsex extensions + HTEST tag
- FHIR resource builders: Patient, Condition, Observation (scalar + multi-component), Encounter, MedicationRequest, Procedure, AllergyIntolerance, Immunization, DiagnosticReport, DocumentReference
- FHIR Bundle (transaction), NDJSON ($export-aligned), and Parquet output
- CLI: `atlas generate`, `atlas validate`, `atlas validate --cohort`, `atlas report`, `atlas modules`, `atlas status`
- Module runtime: time-aware emits, onset dating, progressions, cross-module `requires`
- `atlas ingest` pipeline: prevalence, demographics, and progression overlays with sourced provenance
- Payer/coverage modeling (`--with-coverage`): age-stratified payer mix → Coverage + Organization + InsurancePlan + NAHDO SOPT codes
- Provider/location modeling (`--with-providers`): NPI-keyed Practitioner + PractitionerRole + Location
- Claims (`--with-claims`): Claim + ExplanationOfBenefit per covered Encounter
- SDoH causal overlay (`--with-sdoh`): BRFSS-grounded SDoH sampling; encounter- and medication-adherence causal modifiers; Gravity Project SDOHCC Screening Response Observations for 5 domains
- Quality measure output (`--with-measures`): DEQM-profiled Individual + Summary MeasureReport; 5 HEDIS-analog measures (DM-HbA1c, HTN-BPControl, PreventiveCare, FluVaccine, PedWellChild)
- Clinical notes — template (`--with-notes`): DocumentReference + markdown progress note per condition
- Clinical notes — LLM (`--notes-strategy llm`): Claude-authored Subjective + A&P grounded in structured patient record
- HTML cohort report (`atlas report`): demographics + fidelity table; self-contained single-file output
- Cohort fidelity harness: aggregate metrics vs. sourced expectations, Wilson-interval tolerance, Markdown + JSON scorecard

---

## Milestone 2 — Module Library ✅ Complete (target: 10 modules; achieved: 37)

**Goal:** Prove the module DSL and runtime by authoring high-prevalence clinical conditions across the full care spectrum. Original target was 10 modules; as of this milestone close we have 37 modules across 14 clinical domains.

### Module library (37 modules as of 2026-05-22)

| Domain | Modules |
|---|---|
| Cardiovascular | hypertension, heart_failure, ischemic_heart_disease, atrial_fibrillation, stroke, hypercholesterolemia |
| Metabolic / Endocrine | diabetes (T2D), type1_diabetes, obesity, hypothyroidism |
| Pulmonary | asthma, copd, sleep_apnea, lung_cancer |
| Gastrointestinal | gerd, nafld, inflammatory_bowel_disease |
| Renal | ckd (+ ESRD progression) |
| Musculoskeletal | osteoarthritis, rheumatoid_arthritis |
| Mental health | depression, anxiety, bipolar_disorder |
| Substance use | alcohol_use_disorder, opioid_use_disorder, tobacco_use_disorder |
| Neurology / Cognition | alzheimers_dementia |
| Oncology | lung_cancer, colorectal_cancer, breast_cancer, prostate_cancer |
| Infectious disease | hiv |
| Hematology | sickle_cell (+ vaso-occlusive crisis progression) |
| Pediatric / OB | pediatric_wellness, maternal_health, wellness, complications |
| Prevention | adult_immunizations (8 vaccine cohorts: flu, pneumo, shingles, Tdap, RSV, COVID-19, HPV) |

### Cross-module progressions (active chains)

| From | To | Source |
|---|---|---|
| hypertension | ckd | KDIGO 2024 |
| hypertension | heart_failure | ARIC/Framingham |
| hypertension | stroke | ASA guidelines |
| diabetes | ckd | USRDS 2023 |
| diabetes | retinopathy | WESDR cohort |
| atrial_fibrillation | stroke | CHA₂DS₂-VASc |
| ckd | esrd | USRDS 2023 |
| active_pregnancy | gestational_diabetes | CDC NVSS |
| active_pregnancy | preeclampsia | ACOG |
| active_pregnancy | postpartum_depression | O'Hara 2014 |
| nafld | liver_cirrhosis | Angulo 2002 |
| sickle_cell_disease | vaso_occlusive_crisis | Kauf 2009 |
| type1_diabetes | diabetic_ketoacidosis | AACE/ADA |

---

## Milestone 3 — LLM-Assisted Authoring 🔄 In Progress

**Goal:** Enable faster module authorship through LLM assistance and establish a structured clinician review workflow.

**Delivered:**

- LLM-to-DSL authoring pipeline: ✅ Working (37 modules authored via Claude Code integration)
- Epidemiology citation embedding: ✅ Every module carries `cites:` with source, URL, and summary
- Automated validation loop: ✅ smoke-test + full test suite on every authoring batch
- Authoring workflow documentation: ⏳ Module authoring guide not yet written

**Remaining:**

- Formal clinician review UI (web-based) for sign-off workflow
- Authoring documentation: `docs/authoring/module_dsl.md` spec
- Automated prevalence validation for all 37 modules against sourced expectations (currently ~14 modules have sourced fidelity expectations)
- LLM provider abstraction for non-Claude backends

**Exit criteria (revised):** 100 total modules in the library, all with sourced citations; clinician review workflow established with at least one licensed clinician sign-off per module.

---

## Milestone 4 — Clinical Notes 🔄 In Progress

**Goal:** Generate internally-consistent unstructured clinical notes grounded in the structured patient record.

**Delivered:**

- Template-based progress notes: ✅ `--with-notes` emits DocumentReference per condition, structured data → markdown note
- LLM-authored notes: ✅ `--notes-strategy llm` generates Claude-authored Subjective + Assessment & Plan sections grounded in the patient's generated resources
- DocumentReference FHIR resource with `type`, `category`, `context.encounter` linkage: ✅

**Remaining:**

- Discharge summary generator
- Radiology report generator (linked to imaging Procedures)
- Formal clinician fidelity audit (target: ≥80% acceptance by blinded reviewers)
- Structured/unstructured consistency validation

**Exit criteria:** generated notes pass a blinded clinician fidelity audit with ≥80% acceptance rate across three note types (progress note, discharge summary, radiology report).

---

## Milestone 5 — v1.0 Public Release

**Goal:** Ship v1.0 as a signed, validated release with broad clinical coverage and enterprise-grade documentation.

- 100+ clinical modules (37 of 100+ today)
- All modules with sourced prevalence expectations and passing cohort fidelity checks
- Full US Core 6.1 and IPS 2.0 conformance validation on every release
- SMART on FHIR / Bulk Data Access ($export) endpoint
- Sample populations (1M patients) hosted for download with validation scorecard
- Parquet schema stabilized with versioned column spec
- Dual-license go-live: PyPI package, GitHub release, commercial tier fully operational
- Launch announcement timed to an industry event (HIMSS, FHIR DevDays, or HL7 Working Group)
- Validation scorecard published alongside release

**Exit criteria:** 1,000 GitHub stars within 60 days; three signed enterprise licensing agreements; two academic citations in progress.

---

## Post-v1 Directions

- **Longitudinal patient simulation** — drift, disease progression over simulated years, policy-change counterfactuals
- **Genomic and family history generation** — PRS scores, pharmacogenomics, hereditary cancer risk
- **Medical imaging reference integration** — synthetic DICOM for modalities modeled in module Procedures
- **International locales** — IPS conformance, SNOMED CT international edition, non-US demographic distributions
- **Specialty deep-dives** — oncology staging with TNM, cardiology with device therapy, nephrology with dialysis modeling
- **Federation** — multiple Atlas instances sharing module libraries via versioned package registries

---

## Dependencies and Risks

| Risk | Mitigation |
|---|---|
| Clinical reviewer capacity is the binding constraint | Build clinician review queue into M3; prioritize modules by clinical domain relevance |
| Terminology licensing (UMLS) varies internationally | UMLS Affiliate License covers US use; international deployment needs country-specific assessment |
| LLM provider stability | Two provider backends maintained (Anthropic, OpenAI); local model option planned |
| Module quality degrades as library scales | Mandatory sourced citations + fidelity expectations + smoke-test CI gate on every merge |

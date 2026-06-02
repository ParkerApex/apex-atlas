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

## Milestone 2 — Module Library ✅ Complete (target: 10 modules; achieved: 100)

**Goal:** Prove the module DSL and runtime by authoring high-prevalence clinical conditions across the full care spectrum. Original target was 10 modules; as of this milestone close we have 100 modules across 14 clinical domains.

### Module library (100 modules as of 2026-05-22)

| Domain | Modules |
|---|---|
| Cardiovascular | hypertension, heart_failure, ischemic_heart_disease, atrial_fibrillation, stroke, hypercholesterolemia, peripheral_artery_disease, venous_thromboembolism, valvular_heart_disease, cardiomyopathy |
| Metabolic / Endocrine | diabetes (T2D), type1_diabetes, obesity, hypothyroidism, prediabetes, hyperthyroidism, osteoporosis, metabolic_syndrome, pcos, thyroid_nodule |
| Pulmonary | asthma, copd, sleep_apnea, pneumonia, pulmonary_embolism, pulmonary_hypertension, acute_bronchitis |
| Gastrointestinal | gerd, nafld, inflammatory_bowel_disease, chronic_liver_disease, gallbladder_disease, constipation, diverticulitis, pancreatitis |
| Renal / Urology | ckd (+ ESRD progression), urinary_tract_infection, nephrolithiasis, benign_prostatic_hyperplasia, urinary_incontinence, erectile_dysfunction |
| Musculoskeletal | osteoarthritis, rheumatoid_arthritis, low_back_pain, gout, fibromyalgia, lupus, osteoporosis_fracture, chronic_pain |
| Mental health | depression, anxiety, bipolar_disorder, adhd, insomnia, postpartum_depression |
| Substance use | alcohol_use_disorder, opioid_use_disorder, tobacco_use_disorder |
| Neurology / Cognition | alzheimers_dementia, migraine, epilepsy, parkinsons_disease, peripheral_neuropathy, traumatic_brain_injury, autism_spectrum_disorder |
| Oncology | lung_cancer, colorectal_cancer, breast_cancer, prostate_cancer |
| Infectious disease | hiv, influenza, covid19, hepatitis_c, cellulitis, sepsis_survivorship, sexual_health_sti |
| Hematology | sickle_cell (+ vaso-occlusive crisis progression), iron_deficiency_anemia |
| Pediatric / OB / Prevention | pediatric_wellness, maternal_health, wellness, complications, adult_immunizations (8 vaccine cohorts: flu, pneumo, shingles, Tdap, RSV, COVID-19, HPV), dental_caries, endometriosis, fall_risk, frailty, menopause, pressure_injury, uterine_fibroids |
| Dermatology / Allergy | allergic_rhinitis, atopic_dermatitis, psoriasis, melanoma, acne |
| ENT / Ophthalmology | cataract, otitis_media, sinusitis, conjunctivitis, hearing_loss |

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

**Goal:** Keep the 100-module launch library extensible without letting provenance, test coverage, or clinical review quality degrade.

**Delivered:**

- LLM-to-DSL authoring pipeline: ✅ Working (100 modules authored via Claude Code integration)
- Epidemiology citation embedding: ✅ Every module carries `cites:` with source, URL, and summary
- Automated validation loop: ✅ smoke-test + full test suite on every authoring batch
- Launch-demo cohort preset: ✅ `atlas launch-demo`
- GTM validation preset: ✅ `atlas validate --gtm` across 18 sourced launch expectations
- Authoring workflow documentation: ✅ Module authoring guide written ([`docs/authoring/module_dsl.md`](./authoring/module_dsl.md))

**Remaining:**

- Formal clinician review UI (web-based) for sign-off workflow
- Automated prevalence validation for all 100 modules against sourced expectations (currently 28 modules have sourced fidelity expectations; 18 are included in the GTM validation preset)
- LLM provider abstraction for non-Claude backends

**Exit criteria (revised):** 100 total modules in the library, all with sourced citations; clinician review workflow established with at least one licensed clinician sign-off per module.

Current status: module-count and citation requirements are complete; clinician sign-off workflow remains open.

### 100-module launch plan

The v1.0 library target is now complete at 100 modules. The count matters for GTM only because the library remains useful and auditable: every module ships with citations, deterministic smoke tests, representative FHIR emits, and a documented validation tier. The current catalog lives in [`docs/module-catalog.md`](./module-catalog.md).

| Domain | Current modules | Launch status |
|---|---:|---|
| Cardiovascular | 10 | Complete |
| Metabolic / Endocrine | 10 | Complete |
| Pulmonary | 7 | Complete |
| GI / Hepatology | 8 | Complete |
| Renal / Urology | 6 | Complete |
| Musculoskeletal / Rheumatology | 8 | Complete |
| Mental health / Behavioral | 6 | Complete |
| Substance use | 3 | Complete |
| Neurology / Cognition | 7 | Complete |
| Oncology / Hematology | 7 | Complete |
| Infectious disease | 7 | Complete |
| Pediatric / OB / Prevention | 12 | Complete |
| Dermatology / Allergy | 4 | Complete |
| ENT / Ophthalmology | 5 | Complete |

### Module quality tiers

| Tier | Meaning | Required for |
|---|---|---|
| Tier 1 | Citations + sourced fidelity expectations + cohort validation + clinical review | Headline GTM claims and sample cohorts |
| Tier 2 | Citations + representative FHIR emits + smoke tests + pending fidelity expectations | Bundled v1.0 library |
| Tier 3 | Experimental module, clearly labeled, not included in launch claims | Early community review only |

### Batch plan

| Batch | Target | Primary work |
|---|---:|---|
| Batch A | 50 modules | Complete: primary-care, acute-care, allergy/derm, neuro, vascular, and ophthalmology gaps filled |
| Batch B | 75 modules | Complete: specialty breadth added across cardiovascular, endocrine, pulmonary, GI, urology, MSK, neurology, oncology/heme, ID, and ENT |
| Batch C | 100 modules | Complete: launch library, smoke tests, catalog tiering, demo preset, and GTM validation preset |
| Batch D | 100+ modules | Convert remaining high-use modules to Tier 1 and publish sample cohorts |

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

- 100 clinical modules in the launch library
- All modules with sourced prevalence expectations and passing cohort fidelity checks
- Full US Core 6.1 and IPS 2.0 conformance validation on every release
- SMART on FHIR / Bulk Data Access ($export) endpoint
- Sample populations (1M patients) hosted for download with validation scorecard
- Parquet schema stabilized with versioned column spec
- Dual-license go-live: PyPI package, GitHub release, commercial tier fully operational
- Launch announcement timed to an industry event (HIMSS, FHIR DevDays, or HL7 Working Group)
- Validation scorecard published alongside release
- GTM launch assets complete: module catalog, sample cohort downloads, demo scripts, commercial one-pager, security/provenance FAQ
- Public known-limitations page distinguishing sourced, validated, and experimental capabilities

**Exit criteria:** 1,000 GitHub stars within 60 days; three signed enterprise licensing agreements; two academic citations in progress.

See [`docs/gtm.md`](./gtm.md) for the prime-time GTM checklist and launch gates.

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

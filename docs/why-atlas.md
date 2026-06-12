# Why Parker Built Apex Atlas

*Vincent J. Lopez, Founder & CEO, Parker Health, Inc.*

---

Parker Health, Inc. built Apex Atlas because the synthetic patient data we needed to build healthcare AI responsibly did not exist — and the tools that did exist were not going to produce it.

This document explains the reasoning: what we needed, what we found when we looked at existing options, the specific design decisions that set Atlas apart, and what "the nation's best synthetic healthcare data tool" actually means in practice.

---

## The problem we were solving

Parker's core product, APEX, operates at the intersection of clinical data, payer operations, and AI-assisted care workflows. Every layer of that product requires high-quality synthetic patient data:

**AI model training.** Clinical AI models need labeled training data. Real patient data is credentialed, restricted, and comes with substantial compliance obligations. Synthetic data that accurately reflects real-world clinical distributions lets us train and evaluate models without touching production records during early development.

**FHIR integration testing — production-shaped, not schema-only.** APEX integrates with EHRs, payer systems, QHIN participants, and HIE endpoints via FHIR APIs. Testing those integrations requires patient populations that trigger real code paths — patients with hypertension on lisinopril who missed their last appointment, patients with diabetes and a recent HbA1c, patients who transitioned from Medicaid to commercial coverage. Atlas cohorts **mirror those care patterns** (sourced from public epidemiology) and **map to the same FHIR resource graph** you would receive from TEFCA exchange, HIE query/response, Stedi-style claims/eligibility payloads, or CMS Blue Button beneficiary FHIR — so pipelines can be exercised end-to-end, not merely validated against US Core structure definitions.

**Demo environments.** A meaningful product demo requires a realistic patient panel — conditions distributed the way clinicians actually see them, medication lists that reflect current standards of care, clinical notes that read like clinical notes. This isn't cosmetic. A demo with obviously fake data undermines trust in the product's ability to handle real data.

**Population simulation.** Understanding how care interventions ripple through a patient population — a new care management protocol, a change in prior authorization requirements, a new drug coming to market — requires a population you can modify without ethical constraints. Synthetic populations are the only place you can run those experiments.

---

## What we found when we looked at existing tools

### Synthea

[Synthea](https://synthetichealth.github.io/synthea/) (MITRE) is the most widely used open-source synthetic patient generator and the obvious starting point for comparison. We evaluated it seriously and identified a set of structural limitations that ruled it out as a foundation for our work:

**Disease module ceiling.** Synthea's module authoring requires Java and a proprietary state-machine JSON format. The result is a community-authored module library that plateaued around 90 modules, most of which have not been updated in years. Adding a new condition requires significant effort and clinical expertise in an unfamiliar DSL.

**No SDoH causal modeling.** Synthea generates patients with demographic attributes — race, income bracket — but social determinants do not change how those patients behave. A Synthea patient in poverty has the same appointment completion rate and medication adherence as a wealthy one. Real populations don't work that way. For AI models trained on Synthea data, this means the model learns relationships that don't exist and misses ones that do.

**No quality measure output.** HEDIS measures, CMS eCQMs, and DEQM reporting are central to how payers and health systems measure quality. Synthea generates clinical records but produces no MeasureReport resources. Anyone using Synthea for quality measure testing has to build that layer themselves.

**Clinical notes are templated.** Synthea's notes are string-interpolated templates. They are recognizable as synthetic to any clinician on first read. For AI training — where the goal is to teach a model what real clinical language looks like — template-based notes introduce a distribution shift that can be difficult to detect and hard to correct.

**No pediatric/OB coverage.** Synthea has no maternal health module and limited pediatric coverage. A substantial portion of clinical care involves children and reproductive-age women. A generator that doesn't cover these populations can't train models that will be deployed in those contexts.

### MITRE Health Data Simulator and similar tools

Other generators (Health Data Simulator, various academic projects) face variations of the same constraints. Most are research prototypes rather than maintained production tools. Few produce FHIR output that conforms to US Core 6.1, and none that we found combine statistical grounding, SDoH causal modeling, and quality measure output in a single generator.

### Credentialed datasets (MIMIC, UK Biobank)

Datasets built from de-identified real patient data solve the realism problem but introduce their own constraints: institutional review requirements, credentialing delays (often 6-12 months), data use agreements that restrict how you can use and distribute derived artifacts, and the permanent risk that re-identification attacks will improve. They are also retrospective snapshots — you can't modify the population or run counterfactual scenarios.

We use MIMIC and similar datasets for specific research tasks. They are not a substitute for a synthetic generator you can run at will without compliance overhead.

---

## The design decisions that set Atlas apart

### 1. SDoH as a causal variable, not a demographic tag

The single most important design decision in Atlas is modeling social determinants of health as causes — variables that change what resources get generated — rather than attributes that get attached to a patient as metadata.

When a patient in Atlas has a transportation barrier, they miss some outpatient appointments. The Encounter resource simply doesn't get emitted for that visit. When a patient has financial strain, some medications don't get filled. The MedicationRequest is dropped. This changes the data distribution in the same way real barriers change real utilization.

The rates are sourced from BRFSS (transportation barriers, food insecurity, financial strain) and Urban Institute surveys (cost-related medication non-adherence). The causal modifiers are calibrated to approximate BRFSS-reported care avoidance rates by burden level.

AI models trained on Atlas data with SDoH causal modeling will learn — in the training signal, not as a post-hoc label — that certain patient profiles have lower encounter density and medication adherence. That's the relationship clinicians and care managers actually observe.

### 2. Quality measure output as a first-class feature

Healthcare quality measurement is a core use case for synthetic data. Payers use it to build and test HEDIS reporting pipelines. Health systems use it to validate their eCQM implementations. Parker uses it internally to test quality-based care management features.

No other open generator produces MeasureReport resources. Atlas does. Every `--with-measures` run emits DEQM-profiled Individual MeasureReport resources per patient and population-level Summary MeasureReport resources for the cohort. The measures are evaluated from the patient's actual generated resources — an HbA1c Observation in a diabetic patient counts toward the DM-HbA1c numerator — so the measure scores reflect the synthetic care patterns, including the SDoH-driven utilization gaps.

This means you can generate a synthetic ACO population, run it through a quality measurement pipeline, and get plausible HEDIS-analog rates — not hypothetical ones, but rates that reflect the care delivery patterns encoded in the modules.

### 3. Full lifecycle coverage

Healthcare AI that is useful in the real world has to handle pediatric patients, pregnant patients, and the full range of comorbid complexity that clinicians encounter every day. A generator that stops at adult chronic disease is useful for a narrow set of applications.

Atlas covers:

- **Pediatric well-child visits** with the ACIP 2024 immunization schedule, age-appropriate growth measurements, and CDC NHIS-calibrated visit prevalence across four developmental cohorts (infant, toddler, school-age, adolescent).
- **Maternal health and obstetric care** including the full prenatal visit cascade (first trimester through delivery and postpartum), prenatal labs, and three clinical complications — gestational diabetes, preeclampsia, and postpartum depression — each calibrated to ACOG and CDC published rates.
- **100 clinical modules** (as of May 2026) spanning 14 domains — cardiovascular, metabolic/endocrine, pulmonary, GI/hepatology, renal/urology, musculoskeletal/rheumatology, mental health, substance use, neurology, oncology/hematology, infectious disease, pediatric/OB/prevention, dermatology/allergy, and ENT/ophthalmology — with cross-module progressions (hypertension → CKD, hypertension → stroke, diabetes → retinopathy, atrial fibrillation → stroke, CKD → ESRD, NAFLD → cirrhosis, T1D → DKA, sickle cell → vaso-occlusive crisis, and more).

### 4. Statistical grounding with auditable provenance

Every prevalence rate in Atlas traces back to a published source — NHANES, CDC Data Briefs, SEER, AHA guidelines, ACOG practice bulletins. The ingestion pipeline (`atlas ingest prevalence`, `atlas ingest progression`) enforces sourced provenance at import time: placeholder rates are allowed in hand-authored modules but ingested rates must carry citations and be marked `sourced` or `verified`.

The cohort fidelity harness (`atlas validate --cohort`) checks aggregate distributions against these declared targets after generation. A run of 20,000 patients with the hypertension module should show age-stratified prevalence within tolerance of NHANES 2021-2023 published rates. If it doesn't, something is wrong with the module.

This is not a claim that Atlas produces clinically validated data. It is a claim that the statistical targets are traceable to public sources and that deviation from those targets is detectable.

### 5. FHIR-first, profile-conformant output

Atlas is built around FHIR R4 from the ground up, not a proprietary format with a FHIR export bolt-on. Every resource builder targets a named US Core 6.1 profile. SDoH Observations target the Gravity Project SDOHCC Screening Response profile. MeasureReports target the DEQM Individual and Summary profiles. The Bulk Data output follows the FHIR $export NDJSON convention.

This matters for integration testing: if you are testing a FHIR server's ability to handle a Coverage resource linked to an InsurancePlan with a NAHDO SOPT payer type code, Atlas generates exactly that. You don't have to write test fixtures by hand.

### 6. License structure that matches the use case

Atlas is Apache 2.0 for the generator code and module runtime. Research groups, academic medical centers, health system IT teams, and startup engineers can use it, extend it, and publish modules without restriction.

The commercial license covers enterprise use cases that require Parker's involvement: validated releases with SLAs, indemnification, custom module development for specific therapeutic areas, or embedding Atlas within a competing healthcare data platform.

The CLA requirement for contributors ensures Parker can maintain the dual-license structure without incompatible contributions fragmenting the codebase.

---

## Where Atlas fits in the Parker mission

Parker's mission is to make high-quality healthcare data infrastructure accessible — to the researchers who need it for AI development, to the health systems building their own analytics, and to the startups that can't afford to wait years for credentialed dataset access.

Apex Atlas is the foundational layer of that infrastructure. It is where Parker's understanding of clinical populations, payer dynamics, care delivery patterns, and FHIR implementation is encoded in a form that anyone can run, inspect, and build on.

The goal is not to be the most popular synthetic data generator. It is to be the most accurate and the most useful — the one that produces data that actually changes what an AI model learns, that actually tests a real FHIR integration, that actually reflects how social circumstances shape health outcomes.

That is a harder goal, and it will take longer to reach. The 100-module launch library is now in place; the SDoH causal model still needs to incorporate richer joint distributions across domains, and note generation needs to pass a formal clinician fidelity audit. These are known gaps and there are milestones for each.

But the architecture — statistical grounding, causal SDoH modeling, quality measure output, full lifecycle coverage, auditable provenance, FHIR-first design — is in place. Atlas can be extended toward that goal without re-architecture.

---

## Further reading

- [`docs/roadmap.md`](./roadmap.md) — milestone timeline and exit criteria
- [`docs/architecture.md`](./architecture.md) — subsystem design and extension points
- [`README.md`](../README.md) — quick start and implementation status
- [Parker GPX Identifier Specification](https://parkerapex.com/gpx) — the patient identifier standard Atlas implements

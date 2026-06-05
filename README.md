<div align="center">

# Apex Atlas

**Synthetic FHIR patient populations for AI training, integration testing, demos, and quality workflows.**

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](./LICENSE)
[![FHIR R4](https://img.shields.io/badge/FHIR-R4-red.svg)](https://hl7.org/fhir/R4/)
[![FHIR R5](https://img.shields.io/badge/FHIR-R5-red.svg)](https://hl7.org/fhir/R5/)
[![US Core 6.1](https://img.shields.io/badge/US_Core-6.1-green.svg)](https://hl7.org/fhir/us/core/)

**Author:** Vincent J. Lopez, Founder & CEO, Parker Health, Inc.

</div>

---

Apex Atlas generates large-scale, fully synthetic patient populations in FHIR-native format, grounded in public epidemiological data. It is built by [Parker](https://parkerapex.com) to support training healthcare AI models, validating FHIR integrations, populating demo environments, quality-measure testing, and shared data infrastructure across the APEX platform.

Every synthetic patient receives a Parker Global Patient Identifier (GPX) under the synthetic prefix namespace, making Atlas-generated data fully interoperable with the broader APEX ecosystem while remaining clearly distinguishable from production clinical data.

> **Why did Parker build this?** See [`docs/why-atlas.md`](./docs/why-atlas.md) for the full rationale — the problem with existing tools, the design decisions that set Atlas apart, and where it fits in the Parker mission.

## Proof, not promises

Three things you can open right now:

- 📊 **[Fidelity scorecard](./docs/fidelity-scorecard.md)** — all 101 modules carry a sourced expectation; **563/565 strata (99.6%) within tolerance** of their cited public targets.
- 📉 **[SDoH causal benchmark](./docs/sdoh-causal-benchmark.md)** — ambulatory encounters fall **−39%** and medication fills **−32%** as social-risk burden rises. A tag-only generator can't reproduce this; it's the relationship a model needs to learn.
- 🧬 **[`atlas author`](./docs/authoring/research_authoring.md)** — go from a condition name to a citation-grounded draft module **and its sourced fidelity expectation** in one command, gated by clinician sign-off. The library extends itself instead of plateauing.

## What sets Apex Atlas apart

Existing synthetic patient generators share a common set of limitations: disease module libraries that plateau in the dozens, clinical notes that read as obviously templated, and social determinants of health treated as metadata rather than causal variables. Apex Atlas addresses all three — and adds capabilities no other open generator offers:

- **Research-grounded module authoring** — `atlas author` turns a cited research dossier into a draft module *and* its sourced fidelity expectation in a single pass, both validated through the runtime loaders, then gated behind clinician sign-off before promotion. `atlas author research` produces that dossier autonomously — Claude with the web_search tool pulls current prevalence and codes from authoritative public sources (NHANES, CDC, SEER, peer-reviewed epidemiology). This is the antidote to the plateau problem: the library stays current and auditable because every new module arrives validation-ready, with no uncited numbers. No other open generator can extend itself this way.
- **SDoH as a causal simulation variable** — food insecurity, housing instability, transportation barriers, financial strain, and social isolation are sampled from BRFSS-grounded distributions and causally reduce outpatient encounter completion and medication adherence rates. Patients with barriers miss appointments and don't fill prescriptions — not as a tag, but as a change in what resources get generated. The [**SDoH causal-signal benchmark**](./docs/sdoh-causal-benchmark.md) measures the effect end-to-end: ambulatory encounters fall ~39% and medication fills ~32% from zero to high SDoH burden — a gradient a tag-only generator cannot produce.
- **Quality MeasureReport output** — Apex Atlas is the only open generator that emits DEQM-profiled MeasureReport resources alongside patient records. Five HEDIS-analog measures (HbA1c testing in diabetics, BP control in hypertensives, preventive care, flu immunization, pediatric well-child) are evaluated per patient and summarized for the cohort.
- **Full lifecycle coverage** — pediatric well-child visits with the ACIP 2024 immunization schedule, maternal health and obstetric complications, and 101 clinical modules spanning 14 domains (cardiovascular, metabolic, pulmonary, GI, renal/urology, musculoskeletal/rheumatology, mental health, substance use, neurology, oncology/hematology, infectious disease, pediatric/OB/prevention, dermatology/allergy, and ENT/ophthalmology).
- **Grounded clinical notes** — progress notes, H&Ps, and discharge summaries generated with structured-data grounding. LLM-authored notes (Claude, configurable) are available today via `--notes-strategy llm`.
- **Statistical validation against public norms** — every module declares its prevalence sources (NHANES, CDC, SEER, AHA) and the cohort fidelity harness checks aggregate distributions against those targets. The live [**fidelity scorecard**](./docs/fidelity-scorecard.md) reports, per module, how each stratum compares to its cited target (currently 563/565 strata within tolerance; all 101 modules sourced).
- **FHIR-first, always** — R4 and R5 output, US Core 6.1 conformance, FHIR Bulk Data Access-compatible NDJSON, Gravity Project SDOHCC Observations, and DEQM MeasureReport profiles.

## What Apex Atlas is not

Apex Atlas is not trained on, derived from, or in any way informed by restricted datasets such as MIMIC, UK Biobank, or similar credentialed sources. The generator is built exclusively from public, license-clean statistical distributions published by the CDC, NIH, AHA, and ACOG. No synthetic patient in Atlas corresponds to any real person.

## Implementation status

| Component                    | Status                | Notes |
| ---------------------------- | --------------------- | ----- |
| Parker GPX identifier        | ✅ Implemented        | `gpx.py` — spec v1.0, fully tested |
| Demographic sampling         | ✅ ACS-sourced        | age/sex/race/ethnicity from ACS 2024 1-year estimates (B01001/B02001/B03003) |
| `atlas ingest prevalence`    | ✅ Implemented        | CSV + metadata → sourced fidelity expectation YAML with provenance |
| `atlas ingest demographics`  | ✅ Implemented        | CSV + metadata → `references/tables/*.csv` + provenance sidecar |
| `atlas ingest progression`   | ✅ Implemented        | CSV + metadata → `<module>.progressions.yaml` overlay with sourced rates |
| FHIR Patient                 | ✅ Implemented        | US Core 6.1 with race/ethnicity/birthsex extensions + HTEST tag |
| FHIR Condition               | ✅ Implemented        | US Core Problems & Health Concerns |
| FHIR Observation             | ✅ Implemented        | Vital signs, labs, blood pressure (multi-component), SDOHCC |
| FHIR Encounter               | ✅ Implemented        | US Core: outpatient / inpatient / emergency / home / virtual |
| FHIR MedicationRequest       | ✅ Implemented        | US Core MedicationRequest with inline medicationCodeableConcept |
| FHIR Procedure               | ✅ Implemented        | US Core Procedure 6.1 |
| FHIR AllergyIntolerance      | ✅ Implemented        | US Core AllergyIntolerance |
| FHIR Immunization            | ✅ Implemented        | US Core Immunization; ACIP 2024 schedule in pediatric module |
| FHIR DiagnosticReport        | ✅ Implemented        | Groups Observations (lipid panel, CBC, BMP) |
| FHIR Claim + EOB             | ✅ First cut          | `--with-claims`: one Claim + ExplanationOfBenefit per covered Encounter |
| FHIR MeasureReport           | ✅ Implemented        | `--with-measures`: DEQM Individual + Summary MeasureReport; 5 HEDIS-analog measures |
| FHIR Bundle assembly         | ✅ Implemented        | Transaction Bundle, one file per patient |
| `atlas generate`             | ✅ Implemented        | `--format fhir-r4 / ndjson / parquet` |
| `atlas validate`             | ✅ Structural         | Schema + US Core Patient/Condition minimums |
| `atlas validate --cohort`    | ✅ Implemented        | Fidelity harness: aggregate metrics vs. sourced expectations with tolerance |
| `atlas report`               | ✅ Implemented        | Self-contained HTML cohort report (demographics + fidelity) |
| `atlas modules`              | ✅ Implemented        | List and inspect bundled modules |
| Module runtime               | ✅ Implemented        | Time-aware emits, onset dating, cross-module `requires`, progressions |
| Module library               | ✅ 101 modules        | 100-module launch library + `glaucoma` (first `atlas author`-drafted, Tier 3). CV · metabolic/endocrine · pulmonary · GI/hepatology · renal/urology · MSK/rheum · mental health · SUD · neuro/cognition · oncology/heme · ID · pediatric/OB/prevention · derm/allergy · ENT/ophthalmology |
| Fidelity expectations        | ✅ 101 modules         | 18 launch-hardened sourced expectations available through `atlas validate --gtm` |
| Cross-module dependencies    | ✅ Implemented        | `requires: module:cond_id` gates cross-module comorbidity chains |
| State-machine progressions   | ✅ One-hop            | 13+ chains live: HTN→CKD/HF/stroke, DM→CKD/retinopathy, AFib→stroke, CKD→ESRD, NAFLD→cirrhosis, pregnancy→GDM/preeclampsia/PPD, SCD→VOC, T1D→DKA |
| SDoH causal overlay          | ✅ Implemented        | `--with-sdoh`: BRFSS-grounded sampling; encounter + medication adherence modifiers; Gravity Project SDOHCC Observations |
| Payer & coverage             | ✅ Implemented        | `--with-coverage`: age-stratified payer mix → Coverage + Organization + InsurancePlan |
| Providers & locations        | ✅ Implemented        | `--with-providers`: NPI-keyed Practitioner + PractitionerRole + Location + facility Organization |
| Clinical notes (template)    | ✅ Implemented        | `--with-notes`: DocumentReference + markdown progress note per condition |
| Clinical notes (LLM)         | ✅ Implemented        | `--notes-strategy llm`: Claude-authored Subjective + A&P grounded in structured data |
| Pediatric well-child         | ✅ Implemented        | 4 age cohorts (0-2, 3-5, 6-11, 12-17); ACIP 2024 schedule; NIS-Child/Teen rates |
| Maternal health / OB         | ✅ Implemented        | Pregnancy + prenatal cascade + GDM + preeclampsia + postpartum depression |
| LLM-assisted module authoring| ⏳ Milestone 3        | Natural-language → validated module YAML pipeline |
| `atlas author` (dossier→draft)| ✅ Implemented        | Research dossier → draft module + sourced expectation, validated via loader round-trip; clinician sign-off gate + `atlas author promote`. See [`docs/authoring/research_authoring.md`](./docs/authoring/research_authoring.md) |
| `atlas author research`       | ✅ Implemented        | Autonomous dossier generation via Claude + web_search server tool, validated against the dossier contract; `--draft-out` chains straight into synthesis. Requires `anthropic` extra + `ANTHROPIC_API_KEY` |
| FHIR IPS conformance         | ⏳ Post-v1            | International Patient Summary for non-US use cases |
| $export endpoint             | ⏳ Post-v1            | REST API for on-demand Bulk Data generation |

See [`docs/roadmap.md`](./docs/roadmap.md) for milestone timeline and exit criteria.

## Launch Library

Apex Atlas currently ships **101 bundled modules** across 14 clinical domains — the 100-module launch library plus `glaucoma`, the first module drafted by the `atlas author` research pipeline (Tier 3, sourced prevalence, pending clinical review). Every module carries public-source citations and representative FHIR emits; high-priority GTM modules are backed by sourced fidelity expectations and can be checked together with `atlas validate --gtm`.

The launch library is deliberately balanced across GTM use cases:

| Track | Modules | Why it matters |
| --- | ---: | --- |
| Chronic disease and cardiometabolic care | 20 | Primary-care panels, care management, risk adjustment |
| Pulmonary, GI, renal, and MSK | 29 | Specialty workflows and high-volume outpatient testing |
| Mental health, SUD, and neurology | 16 | Whole-person care, utilization variance, longitudinal complexity |
| Oncology, hematology, and infectious disease | 14 | Specialty demos, procedures, diagnostics, staging, survivorship |
| Pediatric, OB, prevention, and immunizations | 12 | Full lifecycle coverage and payer quality programs |
| Dermatology, allergy, ENT, and ophthalmology | 9 | Common ambulatory use cases that make demos feel complete |

Module growth is not just a count. A module is v1-ready when it has public-source citations, deterministic smoke tests, representative FHIR emits, cohort fidelity expectations where prevalence is clinically material, and a documented review status.

See [`docs/module-catalog.md`](./docs/module-catalog.md) for the current module catalog, [`docs/roadmap.md`](./docs/roadmap.md) for the launch-readiness plan, and [`docs/gtm.md`](./docs/gtm.md) for the prime-time checklist.

## Quick start

> Apex Atlas is not yet on PyPI. Install from source.

```bash
git clone https://github.com/ParkerApex/apex-atlas.git
cd apex-atlas
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Generate 10 synthetic FHIR R4 Patient bundles (US Core 6.1)
atlas generate --patients 10 --seed 42 --out ./out
ls ./out
# GPX-SYN-0000000001-8.json  GPX-SYN-0000000002-6.json  …
# generation-metadata.json  # cohort provenance, patient count, and feature flags

# Structurally validate the output
atlas validate ./out

# Generate the curated launch-demo cohort with notes, SDoH, coverage,
# claims, providers, and quality MeasureReports
atlas launch-demo --patients 2500 --out ./atlas-launch-demo
atlas validate ./atlas-launch-demo --gtm

# See what's built
atlas status

# Run the test suite
pytest
```

### Chronic disease modules

```bash
# Run multiple modules together — cross-module progressions fire automatically
atlas generate --patients 500 --seed 42 \
    --module hypertension,diabetes,ischemic_heart_disease \
    --summary --out ./chronic-cohort

# Inspect any module's prevalence sources and conditions
atlas modules --show diabetes
```

### Full clinical record

```bash
# Everything: payer, providers, claims, SDoH, notes, quality measures
atlas generate --patients 200 --seed 42 \
    --module hypertension,diabetes,wellness \
    --with-coverage \
    --with-providers \
    --with-claims \
    --with-sdoh \
    --with-notes \
    --with-measures \
    --summary \
    --out ./full-cohort
```

### Social determinants

```bash
# Sample SDoH risk factors per patient (BRFSS-grounded rates).
# Patients with transport or cost barriers miss outpatient visits and
# don't fill prescriptions — causally, not as a metadata tag.
# Emits Gravity Project SDOHCC Observations for all 5 domains.
atlas generate --patients 500 --seed 42 \
    --module hypertension,diabetes \
    --with-sdoh --summary --out ./sdoh-cohort
```

### Quality measures

```bash
# Emit DEQM MeasureReport resources per patient + population summaries.
# Measures: DM HbA1c testing, HTN BP control, preventive care,
# flu immunization, pediatric well-child visits.
atlas generate --patients 1000 --seed 42 \
    --module hypertension,diabetes,wellness,pediatric_wellness \
    --with-measures --summary --out ./measures-cohort

# Population-level summary reports appear alongside patient bundles:
ls ./measures-cohort/MeasureReport-*.json
```

### Pediatric and maternal health

```bash
# Well-child visits + ACIP 2024 immunization schedule (ages 0-17)
atlas generate --patients 500 --seed 42 \
    --module pediatric_wellness --summary --out ./peds

# Prenatal care + delivery + obstetric complications (females 15-49)
atlas generate --patients 500 --seed 42 \
    --module maternal_health --summary --out ./ob
```

### Output formats

```bash
# FHIR Bulk Data-style NDJSON — one file per resourceType
atlas generate --patients 500 --seed 42 \
    --module hypertension --format ndjson --out ./bulk
ls ./bulk
# Condition.ndjson  Encounter.ndjson  MedicationRequest.ndjson  Patient.ndjson …

# Columnar Parquet for analytics / DataFrame pipelines
pip install -e ".[data]"
atlas generate --patients 500 --seed 42 \
    --module hypertension --format parquet --out ./parquet
# generation-metadata.json is written into every output directory for audit and cohort tracking
```

### Generation metadata

Every `atlas generate` run writes a `generation-metadata.json` file into the output directory. This artifact is a run manifest, not a FHIR resource. It captures synthetic patient count, active modules / illness types, output format, feature flags, and cohort-level audit breadcrumbs for governance and marketing. `atlas validate` ignores this manifest during FHIR structural validation.

Example fields:

- `cohort_id`: generated run identifier
- `generated_at`: UTC timestamp when the cohort was produced
- `output_path`: target output directory
- `requested_patients`: requested synthetic patient count
- `actual_patients`: actual synthetic patient count produced
- `module_names`: list of active clinical modules
- `format`: output format (`fhir-r4`, `ndjson`, `parquet`)
- `profile`: FHIR profile used
- `seed`: RNG seed
- `with_notes`, `with_coverage`, `with_providers`, `with_claims`, `with_sdoh`, `with_measures`: enabled feature flags
- `summary`: optional demographic counts when `--summary` is used

This file makes cohort generation auditable and easy to aggregate over time.

### LLM-authored clinical notes

```bash
# Template-based notes (no API key required)
atlas generate --patients 50 --seed 42 \
    --module hypertension --with-notes --out ./notes-template

# Claude-authored narrative notes (requires ANTHROPIC_API_KEY)
export ANTHROPIC_API_KEY=sk-ant-...
atlas generate --patients 50 --seed 42 \
    --module hypertension \
    --with-notes --notes-strategy llm \
    --out ./notes-llm
```

### Cohort fidelity validation

```bash
# Check that a cohort's prevalence matches CDC/NHANES published rates
atlas generate --patients 20000 --seed 42 --module hypertension --out ./cohort
atlas validate ./cohort --cohort --module hypertension

# HTML report with demographics + fidelity bars (no JS, safe to email)
atlas report ./cohort --module hypertension --out cohort-report.html
# generation-metadata.json captured at generation time provides an audit trail for internal governance
```

### Authoring a new module from research

```bash
# Autonomous: research a condition, draft module + sourced expectation in one step
# (requires the `anthropic` extra and ANTHROPIC_API_KEY)
atlas author research --condition glaucoma --draft-out ./atlas-drafts

# Or synthesize from a dossier you authored by hand / via the deep-research workflow
atlas author synthesize --dossier ./glaucoma.dossier.yaml --out ./atlas-drafts

# A clinician reviews the draft and fills the Signed-off-by: line in SIGNOFF.md,
# then promote installs the validated module + expectation into the library
atlas author promote --draft ./atlas-drafts/glaucoma

# Verify the loop closes: the new module validates against its own sourced expectation
atlas generate --patients 8000 --seed 7 --module glaucoma --out ./g && \
  atlas validate ./g --cohort --module glaucoma
```

See [`docs/authoring/research_authoring.md`](./docs/authoring/research_authoring.md) for the dossier contract and the full workflow.

## Architecture

Apex Atlas is organized as a single Python package with cleanly separated subsystems.

```
apex-atlas/
├── src/parker_atlas/
│   ├── gpx.py              # Parker GPX identifier — spec v1.0
│   ├── cli.py              # atlas command-line interface
│   ├── core/
│   │   ├── demographics.py # ACS-sourced demographic sampling
│   │   ├── payer.py        # Age-stratified payer mix
│   │   ├── provider.py     # NPI-keyed provider / location sampling
│   │   └── sdoh.py         # BRFSS-grounded SDoH profile + causal modifiers
│   ├── modules/
│   │   ├── runtime.py      # Module DSL parser and probability runtime
│   │   └── library/        # 100 bundled YAML clinical modules
│   ├── fhir/               # FHIR resource builders (US Core 6.1)
│   │   ├── measure_report.py   # DEQM MeasureReport (individual + summary)
│   │   └── sdoh_observation.py # Gravity Project SDOHCC Observations
│   ├── measures/           # Quality measure definitions and evaluation
│   ├── notes/              # Clinical note generation (template + LLM)
│   ├── validation/         # Structural validation + cohort fidelity harness
│   ├── ingest/             # Prevalence / demographics / progression ingestion
│   └── references/         # ACS reference tables (age, sex, race, payer mix)
├── tests/
└── docs/                   # Architecture, roadmap, module catalog, rationale
```

See [`docs/architecture.md`](./docs/architecture.md) for the full design.

## Licensing

Apex Atlas is **dual-licensed**:

- **Apache License 2.0** for the generator code, FHIR tooling, and module runtime — suitable for research, education, open-source integration, and non-competing commercial use
- **Apex Atlas Commercial License** for enterprise deployments requiring validated releases, SLAs, indemnification, custom module development, or embedding within a competing healthcare data platform

See [`LICENSE`](./LICENSE) and [`COMMERCIAL.md`](./COMMERCIAL.md) for details. Contact [licensing@parkerapex.com](mailto:licensing@parkerapex.com) for commercial inquiries.

## Contributing

Apex Atlas welcomes contributions — particularly clinical module authorship from licensed healthcare professionals. See [`CONTRIBUTING.md`](./CONTRIBUTING.md). All contributors sign a Contributor License Agreement (CLA) that permits dual-licensing of their contributions.

## Governance

Apex Atlas is maintained by Parker Health, Inc. Specifications referenced by this project — including the [Parker GPX Identifier Specification](https://parkerapex.com/gpx) — are published independently and may be implemented outside the APEX ecosystem under their respective terms.

## Citing Apex Atlas

If Apex Atlas supports your research, please cite:

```bibtex
@software{lopez2026apexatlas,
  author       = {Lopez, Vincent J.},
  title        = {{Apex Atlas: A Synthetic FHIR Patient Population Generator}},
  year         = {2026},
  version      = {0.9},
  publisher    = {Parker Health, Inc.},
  url          = {https://github.com/ParkerApex/apex-atlas},
  note         = {Generates FHIR R4/R5 patient populations grounded in CDC,
                  NHANES, ACS, SEER, AHA, and ACOG public epidemiological data.
                  Implements US Core 6.1, Gravity Project SDOHCC, and DEQM
                  MeasureReport profiles. Apache 2.0 / commercial dual-license.}
}
```

Plain-text format:

> Lopez, V. J. (2026). *Apex Atlas: A Synthetic FHIR Patient Population Generator* (v0.9). Parker Health, Inc. https://github.com/ParkerApex/apex-atlas

If your work specifically uses the SDoH causal modeling, quality measure output, or pediatric/maternal health modules introduced in the v0.9 release, please note the specific capabilities used so reviewers can evaluate the fitness of the synthetic data for your application.

---

<div align="center">

Built by [Parker](https://parkerapex.com) · Parker Health, Inc.

</div>

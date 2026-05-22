<div align="center">

# Apex Atlas

**A next-generation synthetic FHIR patient population generator.**

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](./LICENSE)
[![FHIR R4](https://img.shields.io/badge/FHIR-R4-red.svg)](https://hl7.org/fhir/R4/)
[![FHIR R5](https://img.shields.io/badge/FHIR-R5-red.svg)](https://hl7.org/fhir/R5/)
[![US Core 6.1](https://img.shields.io/badge/US_Core-6.1-green.svg)](https://hl7.org/fhir/us/core/)

**Author:** Vincent J. Lopez, Founder & CEO, Parker Health, Inc.

</div>

---

Apex Atlas generates large-scale, fully synthetic patient populations in FHIR-native format, grounded in public epidemiological data. It is built by [Parker](https://parkerapex.com) to support training healthcare AI models, validating FHIR integrations, populating demo environments, and serving as shared data infrastructure across the APEX platform.

Every synthetic patient receives a Parker Global Patient Identifier (GPX) under the synthetic prefix namespace, making Atlas-generated data fully interoperable with the broader APEX ecosystem while remaining clearly distinguishable from production clinical data.

> **Why did Parker build this?** See [`docs/why-atlas.md`](./docs/why-atlas.md) for the full rationale — the problem with existing tools, the design decisions that set Atlas apart, and where it fits in the Parker mission.

## What sets Apex Atlas apart

Existing synthetic patient generators share a common set of limitations: disease module libraries that plateau in the dozens, clinical notes that read as obviously templated, and social determinants of health treated as metadata rather than causal variables. Apex Atlas addresses all three — and adds capabilities no other open generator offers:

- **SDoH as a causal simulation variable** — food insecurity, housing instability, transportation barriers, financial strain, and social isolation are sampled from BRFSS-grounded distributions and causally reduce outpatient encounter completion and medication adherence rates. Patients with barriers miss appointments and don't fill prescriptions — not as a tag, but as a change in what resources get generated.
- **Quality MeasureReport output** — Apex Atlas is the only open generator that emits DEQM-profiled MeasureReport resources alongside patient records. Five HEDIS-analog measures (HbA1c testing in diabetics, BP control in hypertensives, preventive care, flu immunization, pediatric well-child) are evaluated per patient and summarized for the cohort.
- **Full lifecycle coverage** — pediatric well-child visits with the ACIP 2024 immunization schedule, maternal health and obstetric complications, and 16 chronic disease modules covering the highest-prevalence adult conditions.
- **Grounded clinical notes** — progress notes, H&Ps, and discharge summaries generated with structured-data grounding. LLM-authored notes (Claude, configurable) are available today via `--notes-strategy llm`.
- **Statistical validation against public norms** — every module declares its prevalence sources (NHANES, CDC, SEER, AHA) and the cohort fidelity harness checks aggregate distributions against those targets.
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
| Module library               | ✅ 16 modules         | HTN / DM / HF / IHD / AFib / stroke / COPD / asthma / depression / hypercholesterolemia / obesity / lung cancer / wellness / pediatric wellness / maternal health / complications |
| Fidelity expectations        | ✅ 14 modules         | Sourced from NHANES, SEER, AHA, CDC |
| Cross-module dependencies    | ✅ Implemented        | `requires: module:cond_id` gates cross-module comorbidity chains |
| State-machine progressions   | ✅ One-hop            | Same-module + cross-module; 9+ chains live (CKD, retinopathy, MI, cardiorenal, HTN→HF, HTN→stroke, AFib→stroke, pregnancy complications) |
| SDoH causal overlay          | ✅ Implemented        | `--with-sdoh`: BRFSS-grounded sampling; encounter + medication adherence modifiers; Gravity Project SDOHCC Observations |
| Payer & coverage             | ✅ Implemented        | `--with-coverage`: age-stratified payer mix → Coverage + Organization + InsurancePlan |
| Providers & locations        | ✅ Implemented        | `--with-providers`: NPI-keyed Practitioner + PractitionerRole + Location + facility Organization |
| Clinical notes (template)    | ✅ Implemented        | `--with-notes`: DocumentReference + markdown progress note per condition |
| Clinical notes (LLM)         | ✅ Implemented        | `--notes-strategy llm`: Claude-authored Subjective + A&P grounded in structured data |
| Pediatric well-child         | ✅ Implemented        | 4 age cohorts (0-2, 3-5, 6-11, 12-17); ACIP 2024 schedule; NIS-Child/Teen rates |
| Maternal health / OB         | ✅ Implemented        | Pregnancy + prenatal cascade + GDM + preeclampsia + postpartum depression |
| LLM-assisted module authoring| ⏳ Milestone 3        | Natural-language → validated module YAML pipeline |
| FHIR IPS conformance         | ⏳ Post-v1            | International Patient Summary for non-US use cases |
| $export endpoint             | ⏳ Post-v1            | REST API for on-demand Bulk Data generation |

See [`docs/roadmap.md`](./docs/roadmap.md) for milestone timeline and exit criteria.

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

# Structurally validate the output
atlas validate ./out

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
```

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
```

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
│   │   └── library/        # 16 bundled YAML clinical modules
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

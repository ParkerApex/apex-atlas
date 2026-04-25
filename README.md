<div align="center">

# Parker Atlas

**A next-generation synthetic FHIR patient population generator.**

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](./LICENSE)
[![FHIR R4](https://img.shields.io/badge/FHIR-R4-red.svg)](https://hl7.org/fhir/R4/)
[![FHIR R5](https://img.shields.io/badge/FHIR-R5-red.svg)](https://hl7.org/fhir/R5/)
[![US Core 6.1](https://img.shields.io/badge/US_Core-6.1-green.svg)](https://hl7.org/fhir/us/core/)

</div>

---

Parker Atlas generates large-scale, fully synthetic patient populations in FHIR-native format, grounded in public epidemiological data. It is designed for training healthcare AI models, validating FHIR integrations, populating demo environments, and serving as reference infrastructure for the [Parker APEX](https://parkerapex.com) platform.

Every synthetic patient receives a Parker Global Patient Identifier (GPX) under the synthetic prefix namespace, making Atlas-generated data fully interoperable with the broader Parker ecosystem while remaining clearly distinguishable from production clinical data.

## Why Parker Atlas

Existing synthetic patient generators are constrained by limited disease module libraries, template-based clinical notes that are obviously non-realistic, and weak representation of social determinants and real-world care gaps. Parker Atlas addresses these with:

- **LLM-assisted disease module authoring** — clinicians describe pathways in natural language; the authoring pipeline produces validated, executable modules
- **Grounded clinical notes** — progress notes, H&Ps, and discharge summaries generated with structured-data grounding and style matching
- **Social determinants realism** — missed appointments, medication non-adherence, insurance transitions, and SDoH modeled as first-class concerns
- **Statistical validation against public norms** — every release auto-compared to CDC, NHANES, and SEER reference distributions
- **FHIR-first, always** — R4 and R5 output, US Core 6.1 and IPS conformance, Bulk Data Access ready

## What Parker Atlas is not

Parker Atlas is not trained on, derived from, or in any way informed by restricted datasets such as MIMIC, UK Biobank, or similar credentialed sources. The generator is built exclusively from public, license-clean statistical distributions. No synthetic patient in Atlas corresponds to any real person.

## Implementation status

Parker Atlas is in early development. The current repository is a scaffold — most components described below are design-complete but not yet implemented.

| Component                  | Status           | Notes                                                                    |
| -------------------------- | ---------------- | ------------------------------------------------------------------------ |
| Parker GPX identifier      | ✅ Implemented   | `src/parker_atlas/gpx.py` — spec v1.0, fully tested                      |
| Demographic sampling       | ✅ Sourced       | age_sex / race / ethnicity backed by 2020 Census + 2024 Vintage estimates      |
| Hypertension prevalence    | ✅ Sourced       | NCHS Data Brief 511 (NHANES Aug 2021–Aug 2023) — age- and sex-stratified     |
| `atlas ingest prevalence`  | ✅ Implemented   | CSV + metadata → sourced fidelity expectation YAML, with provenance checks    |
| `atlas ingest demographics`| ✅ Implemented   | CSV + metadata → references/tables/*.csv + provenance sidecar                 |
| FHIR Patient builder       | ✅ Implemented   | US Core 6.1 Patient with race/ethnicity/birthsex extensions + HTEST tag  |
| FHIR Condition builder     | ✅ Implemented   | US Core Problems & Health Concerns (referenced by modules)               |
| FHIR Observation builder   | ✅ Implemented   | Vital signs, labs, blood pressure (multi-component) — US Core profiles    |
| FHIR Encounter builder     | ✅ Implemented   | US Core Encounter: outpatient / inpatient / emergency / home / virtual    |
| FHIR MedicationRequest     | ✅ Implemented   | US Core MedicationRequest with inline medicationCodeableConcept           |
| FHIR Bundle assembly       | ✅ Implemented   | Transaction Bundle, one file per patient                                 |
| `atlas generate`           | ✅ Implemented   | `--format fhir-r4` / `--format ndjson` / `--format parquet`              |
| `atlas validate`           | ✅ Structural    | Schema validation + US Core Patient/Condition minimums                   |
| `atlas validate --cohort`  | ✅ First cut     | Fidelity harness: aggregate metrics vs. declared expectation w/ tolerance |
| `atlas modules`            | ✅ Implemented   | List bundled modules, show details (`atlas modules --show NAME`)         |
| Clinical module runtime    | ✅ Time-aware emits | Conditions sampled with onset date; emits declare `when: today \| onset` for relative timing |
| Module library             | ✅ 6 modules    | 5 sourced (HTN / DM / lipids / asthma / obesity) + complications (placeholder cross-module demo) |
| Fidelity expectations      | ✅ 6 modules    | 5 sourced + complications (placeholder cross-module fidelity check)        |
| Cross-module dependencies  | ✅ Implemented  | `requires: module:cond_id` + `emit_resource_type: Condition` for harness gating |
| State-machine progressions | ✅ One-hop      | `progressions: [{to, after_years, probability}]` declarative transitions |
| Clinical note generation   | ✅ Template     | `--with-notes`: DocumentReference + inline markdown progress note per condition |
| LLM-assisted authoring     | ⏳ Not started   | Milestone 3                                                              |
| LLM-assisted note authoring| ⏳ Not started   | Milestone 4 — `NoteStrategy.LLM` API surface in place                    |

See [`docs/roadmap.md`](./docs/roadmap.md) for timeline and exit criteria.

## Quick start

> Parker Atlas is not yet on PyPI. Install from source to try the current slice.

```bash
git clone https://github.com/ParkerApex/parker-atlas.git
cd parker-atlas
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Generate 10 synthetic FHIR R4 Patient bundles (US Core 6.1)
atlas generate --patients 10 --seed 42 --out ./out
ls ./out
# GPX-SYN-0000000001-8.json  GPX-SYN-0000000002-6.json  …

# Structurally validate what was generated
atlas validate ./out

# Inspect what is and isn't built yet
atlas status

# Run the test suite
pytest
```

Run with the hypertension module so each patient is sampled against
age-bracketed prevalence — Bundles with a positive draw include a
Condition resource referencing the Patient:

```bash
atlas generate --patients 20 --seed 0 --module hypertension --out ./out
atlas modules --show hypertension
```

Print cohort demographics and condition breakdown right after
generation without re-reading the bundles:

```bash
atlas generate --patients 500 --seed 42 --module hypertension --summary --out ./out
```

Or write FHIR Bulk Data-style NDJSON — one file per resourceType,
one resource per line — for ML pipelines and analytics tools:

```bash
atlas generate --patients 500 --seed 42 --module hypertension \
    --format ndjson --out ./bulk
ls ./bulk
# Condition.ndjson  Encounter.ndjson  MedicationRequest.ndjson
# Observation.ndjson  Patient.ndjson
```

Or columnar Parquet (one file per resourceType, with `id`,
`subject_reference`, and `raw_json` columns) for analytics tools that
prefer DataFrames:

```bash
atlas generate --patients 500 --seed 42 --module hypertension \
    --format parquet --out ./parquet
```

Attach a template-based progress note (FHIR DocumentReference, inline
markdown) per fired condition:

```bash
atlas generate --patients 100 --seed 42 --module hypertension \
    --with-notes --out ./cohort-with-notes
```

Check that a cohort's aggregate statistics match the module's declared
fidelity targets (larger N keeps sampling variance inside the tolerance):

```bash
atlas generate --patients 20000 --seed 42 --module hypertension --out ./cohort
atlas validate ./cohort --cohort --module hypertension
```

Planned:

```bash
atlas generate --module type-2-diabetes --out ./t2d  # (more modules)
```

## Architecture

Parker Atlas is organized as a single Python package with clearly separated subsystems. See [`docs/architecture.md`](./docs/architecture.md) for the full design.

```
parker-atlas/
├── src/parker_atlas/
│   ├── gpx.py          # Parker GPX identifier (implemented)
│   ├── cli.py          # Command-line interface (stub)
│   ├── core/           # Simulation engine, lifecycle, scheduling (planned)
│   ├── modules/        # Clinical pathway modules (planned)
│   ├── fhir/           # FHIR resource construction, profiles (planned)
│   ├── notes/          # Clinical note generation (planned)
│   ├── validation/     # Statistical fidelity harness (planned)
│   └── authoring/      # LLM-assisted module authoring (planned)
├── tests/
└── docs/               # Specifications, guides, module catalog
```

## Licensing

Parker Atlas is **dual-licensed**:

- **Apache License 2.0** for the generator code, FHIR tooling, and module runtime — suitable for research, education, open-source integration, and non-competing commercial use
- **Parker Atlas Commercial License** for enterprise deployments requiring validated releases, SLAs, indemnification, custom module development, or embedding within a competing healthcare data platform

See [`LICENSE`](./LICENSE) and [`COMMERCIAL.md`](./COMMERCIAL.md) for details. Contact licensing@parkerapex.com for commercial inquiries.

## Contributing

Parker Atlas welcomes contributions — particularly clinical module authorship from licensed healthcare professionals. See [`CONTRIBUTING.md`](./CONTRIBUTING.md). All contributors sign a Contributor License Agreement (CLA) that permits dual-licensing of their contributions.

## Governance

Parker Atlas is maintained by Parker Health, Inc. Specifications referenced by this project — including the [Parker GPX Identifier Specification](https://parkerapex.com/gpx) — are published independently and may be implemented outside the Parker ecosystem under their respective terms.

## Citing Parker Atlas

If Parker Atlas supports your research, please cite:

```
Parker Health, Inc. (2026). Parker Atlas: A synthetic FHIR patient
population generator. https://github.com/ParkerApex/parker-atlas
```

---

<div align="center">

Built with care by [Parker Health](https://parkerapex.com)

</div>

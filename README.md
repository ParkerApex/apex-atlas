<div align="center">

# Apex Atlas

**Enterprise-grade synthetic FHIR patient populations for healthcare AI, interoperability, and quality reporting.**

[![Documentation](https://img.shields.io/badge/docs-parkerapex.github.io%2Fapex--atlas-3ba9a0.svg)](https://parkerapex.github.io/apex-atlas/)
[![Generator](https://img.shields.io/badge/🧪_Generator-open_in_browser-3ba9a0.svg)](https://parkerapex.github.io/apex-atlas/generator.html)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](./LICENSE)
[![Version](https://img.shields.io/badge/release-v1.1.0-blue.svg)](https://github.com/ParkerApex/apex-atlas/releases/tag/v1.1.0)
[![FHIR R4](https://img.shields.io/badge/FHIR-R4-red.svg)](https://hl7.org/fhir/R4/)
[![US Core 6.1](https://img.shields.io/badge/US_Core-6.1-green.svg)](https://hl7.org/fhir/us/core/)

[Documentation](https://parkerapex.github.io/apex-atlas/) · [**Web generator**](https://parkerapex.github.io/apex-atlas/generator.html) · [Quick start](#installation--quick-start) · [Integration cookbooks](./docs/integration-cookbooks.md) · [Commercial licensing](./COMMERCIAL.md)

**Parker Health, Inc.** · Maintained by [Parker](https://parkerapex.com)

</div>

---

> ## 📦 CMS Connectathon 2026 — Synthetic Bulk-Publish Dataset
>
> **A ready-to-use, download-and-go dataset lives in [`samples/cms-connectathon-2026/`](./samples/cms-connectathon-2026/).** No build step required.
>
> - **20,000 patients** as FHIR Bulk Data (`$export`) NDJSON — Patient, Condition, Encounter, Observation, MedicationRequest, Immunization, Coverage. → [`patients/`](./samples/cms-connectathon-2026/patients/)
> - **SMART Scheduling Links** (`$bulk-publish`) appointment availability — manifest + Location, Schedule, Slot, Appointment. → [`scheduling/`](./samples/cms-connectathon-2026/scheduling/)
> - **Da Vinci Plan-Net** (`$bulk-publish`) payer provider directory. → [`provider-directory/`](./samples/cms-connectathon-2026/provider-directory/)
> - **Readable samples** (pretty-printed FHIR Bundles) so you can eyeball records without opening the large NDJSON — per-patient records (healthy → multi-morbid) at [`patients/examples/`](./samples/cms-connectathon-2026/patients/examples/) and a clinic scheduling walkthrough at [`scheduling/examples/`](./samples/cms-connectathon-2026/scheduling/examples/).
>
> The whole dataset cross-validates — 246,213/246,213 references resolve; see [`conformance-report.md`](./samples/cms-connectathon-2026/conformance-report.md).
>
> **Start here → [`samples/cms-connectathon-2026/README.md`](./samples/cms-connectathon-2026/README.md)** for download and usage instructions.

---

## Executive summary

Apex Atlas is a synthetic patient population generator that produces FHIR-native clinical records at scale. Cohorts are grounded in publicly sourced US epidemiology and designed to mirror aggregate care patterns—prevalence, comorbidity, utilization, payer mix, social-risk effects, and quality-measure numerators—without replicating individual production records or using restricted datasets.

Each synthetic patient receives a [Parker Global Patient Identifier (GPX)](https://parkerapex.com/gpx) under the synthetic namespace, enabling interoperability across the APEX platform while remaining clearly distinguishable from production PHI.

**Primary applications:** AI model development and evaluation · FHIR integration and regression testing · payer and quality-measure workflows · demonstration and sandbox environments · reproducible research cohorts.

## Production FHIR alignment

Atlas output is structured for the same ingestion paths used in live interoperability and payer programs—not schema validation alone.

| Channel | Representative use case | Atlas output |
| --- | --- | --- |
| QHIN / TEFCA | Clinical summary exchange | US Core Patient, Condition, Observation, Encounter, MedicationRequest, Procedure |
| HIE | Longitudinal, multi-source charts | Multi-condition panels, progressions, DocumentReference notes |
| Payer / clearinghouse APIs | Eligibility, claims, remittance | Coverage, Organization, InsurancePlan, Claim, ExplanationOfBenefit |
| CMS Blue Button 2.0 | Medicare beneficiary FHIR | Age-stratified payer mix, Coverage, EOB, chronic-care modules |
| Bulk Data (`$export`) | Large-scale ingestion | NDJSON (urn:uuid or relative refs) and versioned Parquet exports |
| SMART Scheduling Links (`$bulk-publish`) | Appointment availability | Location, Schedule, Slot NDJSON + booking-deep-link/phone/capacity |
| Da Vinci Plan-Net (`$bulk-publish`) | Payer provider directory | Organization/Network, Location, Practitioner, PractitionerRole, HealthcareService, InsurancePlan, Endpoint |
| CARIN Blue Button (C4BB) | Payer patient-access | C4BB profiles on Patient/Coverage/Organization/EOB (`--carin-bb`) |

Atlas does not connect to, ingest from, or replay data from these production systems. Population statistics are calibrated to cited public sources and validated in the [fidelity scorecard](./docs/fidelity-scorecard.md). See [known limitations](./docs/known-limitations.md) and the [security & provenance FAQ](./docs/security-provenance-faq.md).

Detailed generation recipes: [`docs/integration-cookbooks.md`](./docs/integration-cookbooks.md).

## Platform capabilities

- **Clinical module library** — 101 modules across 14 domains, each with public-source citations and representative FHIR emits.
- **Statistical fidelity** — Cohort validation against sourced expectations; [scorecard](./docs/fidelity-scorecard.md) reports 100/100 modules and 565/565 strata within tolerance.
- **SDoH causal modeling** — Social determinants modify encounter completion and medication adherence, not metadata alone. [Benchmark](./docs/sdoh-causal-benchmark.md): −39% ambulatory encounters and −32% medication fills at high burden.
- **Quality reporting** — DEQM-profiled MeasureReport resources; five HEDIS-analog measures with individual and population summaries.
- **Payer and provider context** — Coverage, claims, NPI-keyed practitioners, and facility organizations.
- **Clinical documentation** — Template and optional LLM-authored notes (progress, discharge, radiology) grounded in structured data.
- **Extensible authoring** — `atlas author` pipeline for citation-grounded module development with clinician sign-off. See [research authoring](./docs/authoring/research_authoring.md).
- **Output formats** — FHIR R4/R5 transaction bundles, Bulk Data-style NDJSON, and Parquet with schema versioning.
- **SMART Scheduling Links** — publish open appointment availability (Location, Schedule, Slot) as a SMART Scheduling Links `$bulk-publish` dataset via `atlas publish-scheduling`. See [`docs/smart-scheduling-links.md`](./docs/smart-scheduling-links.md).
- **Da Vinci Plan-Net directory** — publish a payer provider directory (`$bulk-publish`) via `atlas publish-provider-directory`, built from the same provider roster patient encounters use. See [`docs/provider-directory.md`](./docs/provider-directory.md).
- **CARIN Blue Button** — `atlas generate --carin-bb` stamps C4BB profiles + required elements onto Patient/Coverage/Organization/ExplanationOfBenefit.
- **Reproducible & idiomatic exports** — `--as-of` pins the generation date for byte-stable, seed-reproducible cohorts; `--ref-style relative` emits idiomatic FHIR Bulk Data references.
- **Conformance validation** — `atlas validate --refs` (cross-file referential integrity) and `atlas validate --ig` (native structural + profile + reference checks, plus the external HL7 validator when available).

## Validation and governance

| Artifact | Description |
| --- | --- |
| [Fidelity scorecard](./docs/fidelity-scorecard.md) | Per-module comparison to cited public targets |
| [SDoH causal benchmark](./docs/sdoh-causal-benchmark.md) | End-to-end utilization gradient by social-risk burden |
| `generation-metadata.json` | Run manifest: seed, modules, feature flags, cohort provenance |
| [Module catalog](./docs/module-catalog.md) | Tier, fidelity, and review status by module |
| [GTM readiness](./docs/gtm.md) | Launch gates and buyer evaluation checklist |

## Data provenance

Apex Atlas is built exclusively from public, license-clean statistical distributions (CDC, NIH, NHANES, ACS, SEER, AHA, ACOG, BRFSS, and peer-reviewed literature cited per module).

Atlas is **not** trained on, derived from, or informed by MIMIC, UK Biobank, QHIN payloads, HIE extracts, or other credentialed or production clinical datasets. No synthetic patient corresponds to any real individual.

## Module library

101 bundled clinical modules span cardiovascular, metabolic/endocrine, pulmonary, GI/hepatology, renal/urology, musculoskeletal/rheumatology, mental health, substance use, neurology, oncology/hematology, infectious disease, pediatric/OB/prevention, dermatology/allergy, and ENT/ophthalmology.

| Domain focus | Modules | Typical enterprise use |
| --- | ---: | --- |
| Cardiometabolic and chronic disease | 20 | Primary care, care management, risk adjustment |
| Pulmonary, GI, renal, MSK | 29 | Specialty workflows, high-volume outpatient testing |
| Behavioral health and neurology | 16 | Whole-person care, utilization modeling |
| Oncology, hematology, infectious disease | 14 | Specialty integration and diagnostics |
| Pediatric, OB, prevention | 12 | Lifecycle coverage, quality programs |
| Dermatology, allergy, ENT, ophthalmology | 9 | Ambulatory completeness |

Full catalog: [`docs/module-catalog.md`](./docs/module-catalog.md). Roadmap: [`docs/roadmap.md`](./docs/roadmap.md).

## Platform status

| Component | Status | Notes |
| --- | --- | --- |
| GPX identifier (v1.0) | Available | Synthetic namespace; fully tested |
| Demographics (ACS 2024) | Available | Age, sex, race, ethnicity |
| FHIR US Core 6.1 builders | Available | Patient through MeasureReport |
| `atlas generate` | Available | FHIR R4 bundles, NDJSON, Parquet |
| `atlas validate` / `--cohort` / `--gtm` | Available | Structural and statistical validation |
| SDoH overlay (`--with-sdoh`) | Available | Gravity SDOHCC; causal utilization modifiers |
| Payer & claims | Available | `--with-coverage`, `--with-claims` |
| Clinical notes | Available | Template and LLM (`--notes-strategy`) |
| Module authoring (`atlas author`) | Available | Research → draft → clinician promote |
| Dev API (`atlas serve`) | Available | Docker-deployable; see [`docs/deploy.md`](./docs/deploy.md) |
| SMART Scheduling Links (`$bulk-publish`) | Available | `atlas publish-scheduling`; dev API `/scheduling/$bulk-publish` |
| Da Vinci Plan-Net directory (`$bulk-publish`) | Available | `atlas publish-provider-directory` |
| CARIN Blue Button (C4BB) alignment | Available | `atlas generate --carin-bb` (profiles + required elements) |
| Reproducible cohorts (`--as-of`) | Available | Pin the generation date for byte-stable, seed-reproducible runs |
| IPS 2.0 conformance | Planned | Post-v1 international profiles |
| Production SMART / Bulk `$export` | Planned | Dev `$export` available today |

## Installation & quick start

**Requirements:** Python 3.11+

```bash
git clone https://github.com/ParkerApex/apex-atlas.git
cd apex-atlas
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Generate a synthetic cohort
atlas generate --patients 100 --seed 42 --out ./out

# Validate structure
atlas validate ./out

# Launch-ready demo cohort (notes, SDoH, coverage, claims, providers, measures)
atlas launch-demo --patients 2500 --seed 42 --out ./atlas-launch-demo
atlas validate ./atlas-launch-demo --gtm
```

Pre-built sample manifest (10,000 patients): [`samples/launch-demo-10000-patients/MANIFEST.json`](./samples/launch-demo-10000-patients/MANIFEST.json). Build instructions: [`samples/README.md`](./samples/README.md).

**CMS Connectathon 2026 dataset** — a ready-to-use 20,000-patient FHIR Bulk Data (`$export`) population plus a SMART Scheduling Links (`$bulk-publish`) availability dataset: [`samples/cms-connectathon-2026/`](./samples/cms-connectathon-2026/). For a quick look, see the readable per-patient sample records in [`samples/cms-connectathon-2026/patients/examples/`](./samples/cms-connectathon-2026/patients/examples/).

### Web generator

**UI:** [https://parkerapex.github.io/apex-atlas/generator.html](https://parkerapex.github.io/apex-atlas/generator.html)

The generator is a static web page that calls a running `atlas serve` API. Launch it in one of three ways:

#### Option 1 — Local (fastest)

```bash
git clone https://github.com/ParkerApex/apex-atlas.git
cd apex-atlas
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Start the API (default http://127.0.0.1:8080)
atlas serve --port 8080
```

In a browser, open either:

- [GitHub Pages generator](https://parkerapex.github.io/apex-atlas/generator.html?api=http://127.0.0.1:8080) (API URL prefilled), or
- The local file: `docs/generator.html` (set **API base URL** to `http://127.0.0.1:8080`)

Verify the API: `curl http://127.0.0.1:8080/health`

#### Option 2 — Docker

```bash
docker build -t apex-atlas .
docker run --rm -p 8080:8080 apex-atlas
```

Open [generator.html?api=http://127.0.0.1:8080](https://parkerapex.github.io/apex-atlas/generator.html?api=http://127.0.0.1:8080).

#### Option 3 — Hosted (public demo)

Deploy `atlas serve` to your cloud account (Fly.io, Render, Cloud Run). Full steps: [`docs/deploy.md`](./docs/deploy.md).

After deploy, open the generator with your API URL prefilled:

```text
https://parkerapex.github.io/apex-atlas/generator.html?api=https://YOUR-APP.fly.dev
```

Replace `YOUR-APP.fly.dev` with your deployment hostname.

#### GitHub Pages (documentation site)

To publish the landing page and generator from this repo:

1. GitHub → **Settings** → **Pages**
2. **Source:** Deploy from branch `main`, folder `/docs`
3. Site URL: `https://parkerapex.github.io/apex-atlas/`

API reference: [`docs/api.md`](./docs/api.md). The dev server has no authentication — use rate limiting and a reverse proxy for public endpoints. See [`docs/deploy.md`](./docs/deploy.md).

## Common workflows

**Multi-condition chronic panel**

```bash
atlas generate --patients 500 --seed 42 \
  --module hypertension,diabetes,ischemic_heart_disease \
  --summary --out ./chronic-cohort
```

**Full clinical and payer record**

```bash
atlas generate --patients 200 --seed 42 \
  --module hypertension,diabetes,wellness \
  --with-coverage --with-providers --with-claims \
  --with-sdoh --with-notes --with-measures \
  --summary --out ./full-cohort
```

**Bulk Data export**

```bash
atlas generate --patients 5000 --seed 42 \
  --module hypertension,diabetes \
  --format ndjson --out ./bulk-export
```

**SMART Scheduling Links (`$bulk-publish`)**

```bash
# Publish open appointment availability (Location, Schedule, Slot NDJSON + manifest).
atlas publish-scheduling --sites 25 --weeks 2 --seed 42 --out ./scheduling

# Book a subset of an existing cohort into busy slots as Appointments.
atlas generate --patients 2000 --seed 42 --format ndjson --out ./cohort
atlas publish-scheduling --sites 25 --weeks 2 --seed 42 \
  --patients ./cohort/Patient.ndjson --out ./scheduling
```

**Reproducible, interoperable payer export (CARIN Blue Button)**

```bash
# Pin the date (--as-of) for byte-stable runs, emit relative Bulk Data refs,
# and stamp CARIN Blue Button profiles on the payer resources.
atlas generate --patients 500 --seed 42 --as-of 2026-01-01 \
  --module hypertension,diabetes --with-coverage --with-claims \
  --format ndjson --ref-style relative --carin-bb --out ./carin-cohort
```

**Da Vinci Plan-Net provider directory (`$bulk-publish`)**

```bash
atlas publish-provider-directory --out ./provider-directory
```

**Referential-integrity + IG conformance checks**

```bash
# Every Type/id and Bundle fullUrl reference must resolve within the dataset.
atlas validate ./carin-cohort --refs

# Optional: run outputs through the HL7 FHIR validator (auto-downloads the CLI)
# and write a conformance report.
atlas validate ./carin-cohort --ig --ig-report ./conformance.md
```

**Cohort fidelity report**

```bash
atlas generate --patients 20000 --seed 42 --module hypertension --out ./cohort
atlas validate ./cohort --cohort --module hypertension
atlas report ./cohort --module hypertension --out cohort-report.html
```

Additional examples: social determinants, quality measures, pediatric/OB modules, Parquet export, and module authoring — see [`docs/integration-cookbooks.md`](./docs/integration-cookbooks.md) and the CLI reference via `atlas --help`.

## Architecture

```
apex-atlas/
├── src/parker_atlas/
│   ├── gpx.py                 # Parker GPX identifier
│   ├── cli.py                 # Command-line interface
│   ├── core/                  # Demographics, payer, provider, SDoH
│   ├── modules/library/       # 101 clinical module definitions
│   ├── fhir/                  # US Core 6.1 + C4BB + Plan-Net resource builders
│   ├── scheduling/            # SMART Scheduling Links ($bulk-publish)
│   ├── provider_directory/    # Da Vinci Plan-Net directory ($bulk-publish)
│   ├── measures/              # Quality measure evaluation
│   ├── notes/                 # Clinical note generation
│   ├── validation/            # Structural, cohort, referential, and IG checks
│   └── references/            # ACS and epidemiological tables
├── docs/                      # Architecture, catalog, compliance
└── tests/
```

Full design: [`docs/architecture.md`](./docs/architecture.md). Rationale: [`docs/why-atlas.md`](./docs/why-atlas.md).

## Documentation

| Document | Purpose |
| --- | --- |
| [Web generator](https://parkerapex.github.io/apex-atlas/generator.html) | Browser UI for cohort generation and download |
| [Integration cookbooks](./docs/integration-cookbooks.md) | QHIN, HIE, payer, and Blue Button-shaped workflows |
| [SMART Scheduling Links](./docs/smart-scheduling-links.md) | `$bulk-publish` appointment availability (Location/Schedule/Slot) |
| [Da Vinci Plan-Net directory](./docs/provider-directory.md) | `$bulk-publish` payer provider directory (Organization/Practitioner/PractitionerRole/…) |
| [CI & deployments](./docs/ci-and-deploys.md) | CI workflow, and the one-time settings to fix the Pages / PyPI deploys |
| [Known limitations](./docs/known-limitations.md) | Capability boundaries and tier definitions |
| [Security & provenance FAQ](./docs/security-provenance-faq.md) | PHI, licensing, API keys, deployment |
| [Commercial one-pager](./docs/commercial-one-pager.md) | Apache 2.0 vs enterprise license |
| [API reference](./docs/api.md) | `atlas serve` endpoints |
| [Deploy guide](./docs/deploy.md) | Docker, Fly, Render, Cloud Run |

## Licensing

Apex Atlas is dual-licensed:

- **Apache License 2.0** — generator code, FHIR tooling, and module runtime for research, education, and non-competing commercial use.
- **Apex Atlas Commercial License** — enterprise deployments requiring validated releases, SLAs, indemnification, custom modules, or embedding in competing synthetic-data platforms.

See [`LICENSE`](./LICENSE) and [`COMMERCIAL.md`](./COMMERCIAL.md). Enterprise inquiries: [licensing@parkerapex.com](mailto:licensing@parkerapex.com).

## Contributing

Contributions are welcome, particularly clinical module authorship from licensed healthcare professionals. See [`CONTRIBUTING.md`](./CONTRIBUTING.md). All contributors sign a Contributor License Agreement (CLA) supporting dual licensing.

## Governance

Apex Atlas is maintained by **Parker Health, Inc.** Specifications referenced by this project—including the [Parker GPX Identifier Specification](https://parkerapex.com/gpx)—are published independently and may be implemented outside the APEX ecosystem under their respective terms.

## Citation

```bibtex
@software{lopez2026apexatlas,
  author       = {Lopez, Vincent J.},
  title        = {{Apex Atlas: A Synthetic FHIR Patient Population Generator}},
  year         = {2026},
  version      = {1.1.0},
  publisher    = {Parker Health, Inc.},
  url          = {https://github.com/ParkerApex/apex-atlas},
  note         = {Generates FHIR R4/R5 patient populations grounded in public
                  US epidemiological data. Implements US Core 6.1, Gravity
                  Project SDOHCC, and DEQM MeasureReport profiles.}
}
```

Plain text:

> Lopez, V. J. (2026). *Apex Atlas: A Synthetic FHIR Patient Population Generator* (v1.1.0). Parker Health, Inc. https://github.com/ParkerApex/apex-atlas

---

<div align="center">

Copyright © 2026 Parker Health, Inc. · [parkerapex.com](https://parkerapex.com)

</div>

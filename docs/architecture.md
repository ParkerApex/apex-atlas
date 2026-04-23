# Parker Atlas Architecture

## Overview

Parker Atlas is a modular synthetic patient generator organized around four layers: a simulation core, a clinical module runtime, a FHIR output pipeline, and an LLM-assisted authoring toolchain. Each layer has clear interfaces so that components can be replaced or extended independently.

```
                    ┌─────────────────────────────────────┐
                    │        Authoring Toolchain          │
                    │  (LLM-assisted module authoring)    │
                    └─────────────────┬───────────────────┘
                                      │ produces
                                      ▼
┌──────────────┐   ┌──────────────────────────────────┐   ┌──────────────┐
│ Public Data  │──▶│         Module Library            │──▶│  Validation  │
│  Sources     │   │  (disease & care pattern modules) │   │   Harness    │
└──────────────┘   └─────────────────┬────────────────┘   └──────┬───────┘
                                     │                           │
                                     ▼                           │
                   ┌─────────────────────────────────┐           │
                   │       Simulation Core            │           │
                   │ (patient lifecycle, scheduler,   │           │
                   │  demographics, event sequencing) │◀──────────┘
                   └─────────────────┬────────────────┘
                                     │
                      ┌──────────────┼──────────────┐
                      ▼              ▼              ▼
               ┌───────────┐  ┌───────────┐  ┌───────────┐
               │    GPX    │  │   FHIR    │  │  Clinical │
               │ Allocator │  │ Resources │  │   Notes   │
               └───────────┘  └───────────┘  └───────────┘
                                     │
                                     ▼
                   ┌──────────────────────────────────┐
                   │         Output Formats            │
                   │  FHIR Bundle │ NDJSON │ Parquet   │
                   └──────────────────────────────────┘
```

## Package layout

```
parker-atlas/
├── src/parker_atlas/
│   ├── core/            # Simulation engine
│   │   ├── patient.py      # Patient lifecycle object
│   │   ├── scheduler.py    # Discrete-event scheduler
│   │   ├── demographics.py # Age, sex, race, SDoH sampling
│   │   └── population.py   # Population-level generation orchestration
│   ├── modules/         # Clinical pathway modules
│   │   ├── runtime.py      # Module state machine executor
│   │   ├── dsl.py          # Module DSL parser and validator
│   │   └── library/        # Bundled module definitions (YAML)
│   ├── fhir/            # FHIR resource construction
│   │   ├── patient.py      # Patient resource builder
│   │   ├── encounter.py    # Encounter, Condition, Observation
│   │   ├── medication.py   # Medication, MedicationRequest
│   │   ├── profiles.py     # US Core 6.1 and IPS conformance
│   │   └── bundle.py       # Bundle assembly and Bulk Data export
│   ├── gpx.py           # Parker GPX identifier (spec v1.0)
│   ├── notes/           # Clinical note generation
│   │   ├── grounding.py    # Structured-data grounding layer
│   │   ├── styles.py       # Clinical voice matching
│   │   └── generators/     # Note-type-specific generators
│   ├── validation/      # Statistical validation harness
│   │   ├── references.py   # Public norm datasets (CDC, NHANES, SEER)
│   │   ├── fidelity.py     # Distribution comparison methods
│   │   └── reports.py      # Fidelity scorecards
│   ├── authoring/       # LLM-assisted module authoring
│   │   ├── scaffold.py     # Natural language to module DSL
│   │   ├── review.py       # Clinician review interface
│   │   └── providers/      # LLM provider abstractions
│   ├── cli.py           # Typer-based CLI
│   └── config.py        # Configuration loading
├── tests/
├── docs/
│   ├── architecture.md     # This file
│   ├── authoring/          # Module authoring guide
│   └── gpx-spec.md         # Mirror of Parker GPX Spec v1.0
└── data/
    └── references/         # Public statistical reference data
```

## Design principles

**License cleanliness.** Parker Atlas is built exclusively from public, redistributable sources. No credentialed dataset (MIMIC, UK Biobank, etc.) touches the training or generation pipeline. This is enforced by a data provenance manifest reviewed on every release.

**FHIR-first, not FHIR-after.** Internal patient state is modeled to map cleanly to FHIR resources. Generators produce FHIR resources directly rather than translating from an internal schema.

**Modularity over monolith.** Each clinical module is a self-contained state machine that can be loaded, updated, or disabled independently. This enables an iterative module library that can grow to hundreds of pathways without destabilizing the generator core.

**Statistical traceability.** Every rate, probability, and distribution in a module cites a public source. The validation harness verifies that aggregate synthetic output matches the cited distributions within tolerance.

**LLM-optional.** The core generator runs without any LLM. LLMs are used for two opt-in features: authoring assistance (offline, at module creation time) and clinical note generation (at runtime, swappable provider).

## Simulation Core

The core is a discrete-event simulator. Each patient has a timeline of events (birth, encounters, diagnoses, medications, observations, social events). Modules are state machines that subscribe to patient state changes and emit new events.

**Execution model:** patients are simulated independently and in parallel. A population of 10 million patients parallelizes linearly across cores. The scheduler is lock-free per patient, with shared read-only module definitions.

**Time model:** simulated time advances from patient birth to a configurable end date (default: current date). Events carry simulated timestamps; wall-clock time is irrelevant to output.

## Module Library

Modules are authored in a YAML-based DSL. See [`docs/authoring/module_dsl.md`](authoring/module_dsl.md) for the full specification. A minimal module:

```yaml
module: type-2-diabetes
version: 1.0.0
cites:
  - source: cdc.gov/diabetes/data/statistics-report
    url: https://www.cdc.gov/diabetes/data/statistics-report/
states:
  initial:
    type: branch
    next:
      - probability: 0.115   # US adult T2D prevalence
        to: diagnosed
      - probability: 0.885
        to: not_diagnosed
  diagnosed:
    type: condition
    code: { system: snomed, code: "44054006", display: "Type 2 diabetes mellitus" }
    next: first_line_therapy
  first_line_therapy:
    type: medication
    code: { system: rxnorm, code: "860975", display: "Metformin 500 MG" }
    duration: { distribution: exponential, mean_years: 5.2 }
```

## FHIR output

Output is always valid FHIR. Conformance is verified by the `fhir.resources` Pydantic models and by optional round-tripping through HAPI FHIR validation. US Core 6.1 profile conformance is the default; IPS and base FHIR are available via CLI flag.

**Formats:**
- FHIR Bundle JSON — one file per patient, transaction bundle
- NDJSON — one resource per line, aligned to FHIR Bulk Data Access ($export)
- Parquet — columnar, one file per resource type, for data science workloads

Every Patient resource includes a GPX identifier in the SYN category. Every resource includes the HL7 HTEST meta tag.

## Validation Harness

After each generation run, the harness compares synthetic output against public norms:

- Age and sex distribution vs. US Census ACS
- Disease prevalence vs. CDC BRFSS and NHANES
- Cancer incidence vs. SEER aggregates
- Medication utilization vs. Medicare Part D public data
- Lab value distributions vs. NHANES

Results are emitted as a Markdown fidelity scorecard plus a machine-readable JSON summary. A module that fails its declared validation expectations blocks release.

## Authoring Toolchain

Module authoring is the differentiator. The flow:

1. A clinician describes a disease pathway in natural language ("Type 2 diabetes typically presents with..., is diagnosed by..., first-line therapy is..., progresses to...")
2. The authoring tool, backed by an LLM, generates a draft module in the YAML DSL
3. The tool automatically pulls epidemiology from open-access sources and populates rates
4. A validation pass checks the module against the statistical harness
5. The clinician reviews, edits, and signs off
6. The module is submitted as a pull request with provenance metadata

The LLM provider is abstracted; Parker's reference implementation supports Anthropic Claude and OpenAI, with an option for self-hosted open models.

## Non-goals

- Parker Atlas does not simulate healthcare economics, reimbursement, or claims adjudication at payer-level detail. These can be added as modules but are not core.
- Parker Atlas does not generate medical images. Imaging is referenced by DICOM identifiers; actual pixel synthesis is out of scope for v1.
- Parker Atlas does not replace domain-specific generators (genomic simulators, pharmacokinetic models). It can interoperate with them via standard FHIR references.

## Roadmap

See [`docs/roadmap.md`](roadmap.md) for the current milestone plan.

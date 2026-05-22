# APEX Atlas Architecture

## Overview

APEX Atlas is a modular synthetic patient generator organized around four layers: a simulation core, a clinical module runtime, a FHIR output pipeline, and an LLM-assisted authoring toolchain. Each layer has clear interfaces so that components can be replaced or extended independently.

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
│   ├── core/               # Simulation support
│   │   ├── demographics.py     # Age/sex/race/ethnicity sampling from ACS 2024
│   │   ├── sdoh.py             # SDoH profile sampling + causal modifiers (BRFSS)
│   │   ├── payer.py            # Age-stratified payer mix sampling
│   │   └── provider.py         # NPI-keyed provider/location assignment
│   ├── modules/            # Clinical pathway modules
│   │   ├── runtime.py          # Module DSL parser + probability runtime
│   │   └── library/            # 37 bundled module YAMLs (growing toward 100+)
│   ├── fhir/               # FHIR R4 resource construction
│   │   ├── patient.py          # US Core 6.1 Patient
│   │   ├── condition.py        # US Core Condition
│   │   ├── observation.py      # Vital signs, labs, multi-component (BP)
│   │   ├── sdoh_observation.py # Gravity Project SDOHCC Screening Response
│   │   ├── encounter.py        # US Core Encounter (AMB/EMER/IMP/HH/VR)
│   │   ├── medication_request.py  # US Core MedicationRequest
│   │   ├── procedure.py        # US Core Procedure
│   │   ├── allergy_intolerance.py # US Core AllergyIntolerance
│   │   ├── immunization.py     # US Core Immunization (CVX codes)
│   │   ├── diagnostic_report.py   # US Core DiagnosticReport (lab panels)
│   │   ├── document_reference.py  # Clinical notes (template + LLM)
│   │   ├── measure_report.py   # DEQM Individual + Summary MeasureReport
│   │   ├── coverage.py         # US Core Coverage + InsurancePlan + Org
│   │   ├── claim.py            # Claim + ExplanationOfBenefit
│   │   ├── practitioner.py     # US Core Practitioner + PractitionerRole
│   │   ├── location.py         # US Core Location
│   │   ├── organization.py     # US Core Organization (payer + facility)
│   │   ├── mortality.py        # Deceased flag + cause-of-death linking
│   │   └── bundle.py           # Transaction Bundle + NDJSON assembly
│   ├── measures/           # Quality measure evaluation
│   │   └── __init__.py         # 5 HEDIS-analog measures; MeasureTally; evaluate_measures()
│   ├── ingest/             # Data ingestion pipeline
│   │   ├── prevalence.py       # CSV + metadata → sourced fidelity expectation YAML
│   │   ├── demographics.py     # CSV + metadata → references/tables/ + provenance sidecar
│   │   └── progression.py      # CSV + metadata → <module>.progressions.yaml overlay
│   ├── notes/              # Clinical note generation
│   │   ├── progress.py         # Template-based markdown progress note
│   │   └── llm.py              # LLM-authored Subjective + A&P (Claude API)
│   ├── validation/         # Statistical validation harness
│   │   ├── cohort.py           # Aggregate metric comparison vs. sourced expectations
│   │   ├── structural.py       # Schema + US Core Patient/Condition minimums
│   │   ├── report.py           # Fidelity scorecard (Markdown + JSON)
│   │   └── expectations/library/  # Sourced fidelity expectation YAMLs (14 modules)
│   ├── references/tables/  # Demographic reference CSVs (ACS age/sex/race/ethnicity)
│   ├── gpx.py              # Parker GPX identifier (deterministic UUID5 namespace)
│   └── cli.py              # Typer CLI: generate / validate / report / modules / status / ingest
├── tests/
├── docs/
│   ├── architecture.md     # This file
│   ├── roadmap.md          # Milestone plan (updated 2026-05-22)
│   ├── why-atlas.md        # Strategic rationale (V.J. Lopez)
│   └── ingestion.md        # atlas ingest usage guide
└── pyproject.toml
```

## Design principles

**License cleanliness.** APEX Atlas is built exclusively from public, redistributable sources. No credentialed dataset (MIMIC, UK Biobank, etc.) touches the training or generation pipeline. This is enforced by a data provenance manifest reviewed on every release.

**FHIR-first, not FHIR-after.** Internal patient state is modeled to map cleanly to FHIR resources. Generators produce FHIR resources directly rather than translating from an internal schema.

**Modularity over monolith.** Each clinical module is a self-contained state machine that can be loaded, updated, or disabled independently. This enables an iterative module library that can grow to hundreds of pathways without destabilizing the generator core.

**Statistical traceability.** Every rate, probability, and distribution in a module cites a public source. The validation harness verifies that aggregate synthetic output matches the cited distributions within tolerance.

**LLM-optional.** The core generator runs without any LLM. LLMs are used for two opt-in features: authoring assistance (offline, at module creation time) and clinical note generation (at runtime, swappable provider).

## Simulation Core

The core is a discrete-event simulator. Each patient has a timeline of events (birth, encounters, diagnoses, medications, observations, social events). Modules are state machines that subscribe to patient state changes and emit new events.

**Execution model:** patients are simulated independently and in parallel. A population of 10 million patients parallelizes linearly across cores. The scheduler is lock-free per patient, with shared read-only module definitions.

**Time model:** simulated time advances from patient birth to a configurable end date (default: current date). Events carry simulated timestamps; wall-clock time is irrelevant to output.

## Module Library

Modules are authored in a YAML-based DSL. A minimal module illustrating the key structural elements:

```yaml
module: hypothyroidism
version: 0.1.0
description: >
  Primary hypothyroidism module. Prevalence ~4.6% overall (Hollowell NHANES III);
  female-dominant with marked age gradient. Levothyroxine in 90% of diagnosed patients.
cites:
  - source: >
      Hollowell JG et al. Serum TSH, T4, and thyroid antibodies in the US
      population (NHANES III). J Clin Endocrinol Metab. 2002;87(2):489-499.
    url: https://academic.oup.com/jcem/article/87/2/489/2846790
    summary: >
      Overall prevalence 4.6% (TSH >4.5 mIU/L or thyroid medication).
      Female ~7-8%, male ~2-3%. Rises with age.
conditions:
  - id: hypothyroidism
    code:
      system: http://snomed.info/sct
      code: "40930008"
      display: Hypothyroidism (disorder)
    prevalence:
      female:
        "0-17":  0.005
        "18-39": 0.030
        "40-59": 0.075
        "60-99": 0.130
      male:
        "0-17":  0.002
        "18-39": 0.012
        "40-59": 0.025
        "60-99": 0.055
    onset_age:
      min: 18
      max: 85
    emits:
      - resource_type: Encounter
        spec_id: thyroid_followup_visit
        when: today
        encounter_class: AMB
        type:
          system: http://snomed.info/sct
          code: "390906005"
          display: Follow-up encounter (procedure)
        reason:
          system: http://snomed.info/sct
          code: "40930008"
          display: Hypothyroidism
      - resource_type: Observation
        spec_id: thyroid_tsh
        when: today
        link_to: thyroid_followup_visit
        category: laboratory
        code:
          system: http://loinc.org
          code: "3016-3"
          display: Thyrotropin [Units/volume] in Serum or Plasma
        value_range: {low: 4.6, high: 50.0, precision: 1}
        unit: mIU/L
        unit_code: m[IU]/L
      - resource_type: MedicationRequest
        spec_id: thyroid_levothyroxine
        when: today
        link_to: thyroid_followup_visit
        probability: 0.90
        medication:
          system: http://www.nlm.nih.gov/research/umls/rxnorm
          code: "892245"
          display: Levothyroxine Sodium 50 MCG Oral Tablet
```

Each `conditions` entry maps to one `Condition` FHIR resource. `emits` entries are sampled at generation time: all emits without `probability` are unconditional; those with `probability` fire as Bernoulli trials. `link_to` references another emit's `spec_id` to set the `encounter` reference on the emitted resource. `when: onset` back-dates the resource to the patient's condition onset date; `when: today` uses the simulated current date.

## FHIR output

Output is always valid FHIR. Conformance is verified by the `fhir.resources` Pydantic models and by optional round-tripping through HAPI FHIR validation. US Core 6.1 profile conformance is the default; IPS and base FHIR are available via CLI flag.

**Formats:**
- FHIR Bundle JSON — one file per patient, transaction bundle
- NDJSON — one resource per line, aligned to FHIR Bulk Data Access ($export)
- Parquet — columnar, one file per resource type, for data science workloads
- generation-metadata.json — run-level provenance, patient counts, CLI feature flags, and optional summary metrics

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

- APEX Atlas does not simulate healthcare economics, reimbursement, or claims adjudication at payer-level detail. These can be added as modules but are not core.
- APEX Atlas does not generate medical images. Imaging is referenced by DICOM identifiers; actual pixel synthesis is out of scope for v1.
- APEX Atlas does not replace domain-specific generators (genomic simulators, pharmacokinetic models). It can interoperate with them via standard FHIR references.

## Roadmap

See [`docs/roadmap.md`](roadmap.md) for the current milestone plan.

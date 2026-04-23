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

## Quick start

```bash
# Install from PyPI
pip install parker-atlas

# Generate 1,000 synthetic patients, FHIR R4 Bundle output
atlas generate --patients 1000 --format fhir-r4 --out ./patients/

# Validate against US Core 6.1
atlas validate ./patients/ --profile us-core-6.1

# Run a specific clinical module
atlas generate --patients 100 --module type-2-diabetes --out ./t2d/
```

## Architecture

Parker Atlas is organized as a monorepo of focused packages. See [`docs/architecture.md`](./docs/architecture.md) for the full design.

```
parker-atlas/
├── core/            # Simulation engine, patient lifecycle, event scheduling
├── modules/         # Clinical pathway modules (diseases, care patterns)
├── fhir/            # FHIR resource construction, US Core, IPS profiles
├── gpx/             # Parker GPX identifier allocation and validation
├── notes/           # LLM-based clinical note generation
├── validation/      # Statistical fidelity harness vs. public norms
├── cli/             # Command-line interface
├── authoring/       # LLM-assisted module authoring pipeline
└── docs/            # Specifications, guides, module catalog
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
population generator. https://github.com/parker-health/parker-atlas
```

---

<div align="center">

Built with care by [Parker Health](https://parkerapex.com)

</div>

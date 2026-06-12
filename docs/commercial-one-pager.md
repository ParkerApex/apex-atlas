# Apex Atlas — Commercial One-Pager

**Synthetic FHIR patient populations for healthcare AI, integration testing, and quality workflows.**

---

## Problem

Teams need realistic FHIR data at scale without PHI friction, credentialed dataset delays, or license ambiguity. Tag-only generators produce unrealistic utilization and cannot support measure testing or SDoH-aware models.

## Solution

**Apex Atlas** generates fully synthetic, FHIR-native patient populations grounded in public US epidemiology — cohorts that **mirror real care distributions** and **map to production ingestion paths** (QHIN/TEFCA, HIE, Stedi-style claims, CMS Blue Button-shaped FHIR) — with GPX identifiers, US Core 6.1 output, optional SDoH causal modeling, claims, and DEQM MeasureReports.

## What you get (Apache 2.0)

- CLI: `atlas generate`, `validate`, `report`, `modules`, `launch-demo`
- **101 clinical modules** across 14 domains
- Formats: FHIR R4 bundles, Bulk-style NDJSON, Parquet
- Cohort fidelity validation vs. cited CDC/NHANES/ACS targets
- Module DSL + `atlas author` research pipeline for extensibility

Install from source today; PyPI package at v1.0.

## When to buy commercial

| Need | Apache 2.0 | Commercial |
| --- | --- | --- |
| Research, education, non-competing integration | ✅ | Optional support |
| Validated release artifacts + scorecards | Community | ✅ Signed releases |
| SLA, indemnification, liability cap | — | ✅ |
| Custom modules (your pathways, your codes) | Contribute via CLA | ✅ Services |
| Embedding in a **competing** synthetic-data platform | ❌ | ✅ License required |
| Priority support & roadmap input | — | ✅ |

Contact: **[licensing@parkerapex.com](mailto:licensing@parkerapex.com)**

## Proof points

- [Fidelity scorecard](./fidelity-scorecard.md) — 100 modules, 99.6% strata within tolerance
- [SDoH causal benchmark](./sdoh-causal-benchmark.md) — utilization gradient, not tags
- `atlas launch-demo` — rich demo cohort in one command
- [Known limitations](./known-limitations.md) — honest capability boundaries

## Typical buyers

- Healthcare AI startups (training/eval without PHI)
- Health system FHIR integration teams (US Core test panels)
- Payers & quality vendors (MeasureReport + claims-like data)
- Academic researchers (license-clean, reproducible seeds)

## Deployment options

- **Local / CI** — Python package, deterministic seeds
- **Bulk files** — NDJSON/Parquet for warehouses
- **Demo API** — Docker + `atlas serve` (your cloud, your keys)

## About Parker

Apex Atlas is maintained by **Parker Health, Inc.** — building shared synthetic data infrastructure for the APEX platform.

- Website: [parkerapex.com](https://parkerapex.com)
- Repository: [github.com/ParkerApex/apex-atlas](https://github.com/ParkerApex/apex-atlas)
- Atlas: [atlas@parkerapex.com](mailto:atlas@parkerapex.com)

---

*Apache 2.0 does not grant trademark rights to “Apex Atlas” or “Parker.” Commercial terms in [COMMERCIAL.md](../COMMERCIAL.md).*

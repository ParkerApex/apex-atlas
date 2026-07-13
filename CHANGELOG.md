# Changelog

All notable changes to Apex Atlas are documented here. This project adheres to
[Semantic Versioning](https://semver.org/).

## [1.1.0] — 2026-07-13

Interoperability & CMS-alignment release ("Milestone 6").

### Added
- **SMART Scheduling Links** (`$bulk-publish`): `atlas publish-scheduling`
  emits Location / Schedule / Slot NDJSON + a manifest, with the SMART
  booking-deep-link / booking-phone / slot-capacity extensions; also served by
  the dev API at `GET /scheduling/$bulk-publish`.
- **Da Vinci PDEX Plan-Net** provider directory (`$bulk-publish`):
  `atlas publish-provider-directory` emits Organization/Network, Location,
  Practitioner, PractitionerRole, HealthcareService, InsurancePlan, and
  Endpoint. Built from the same provider roster patient encounters use, so
  claim ↔ directory NPIs are coherent.
- **CARIN Blue Button (C4BB)** alignment: `atlas generate --carin-bb` stamps
  C4BB profiles + required top-level elements onto Patient / Coverage /
  Organization / ExplanationOfBenefit.
- **Reproducible generation**: `atlas generate --as-of DATE` pins the generation
  date so `--seed` runs are byte-stable and don't drift day to day (recorded in
  `generation-metadata.json`).
- **Idiomatic Bulk Data references**: `atlas generate --ref-style relative`
  emits `Patient/<id>` references instead of `urn:uuid:`.
- **Referential integrity validation**: `atlas validate --refs` resolves every
  reference across NDJSON, `$bulk-publish` datasets, and R4 Bundles.
- **IG conformance harness**: `atlas validate --ig` runs native structural +
  profile + reference checks, plus the external HL7 FHIR validator when a
  `validator_cli.jar` is available; writes a Markdown report.
- **CI**: `.github/workflows/ci.yml` runs pytest on Python 3.11 / 3.12
  (blocking) with ruff + mypy advisory.
- **CMS Connectathon 2026 dataset** under `samples/cms-connectathon-2026/`: a
  fully cross-validating three-part bundle (20k-patient `$export` + SMART
  Scheduling Links + Plan-Net) with a shipped `conformance-report.md`
  (246,084/246,084 references resolved; 168,237/168,237 resources valid).

### Fixed
- Date-drift test failure (`test_module_copd`) resolved by `--as-of` pinning.
- `validate` reference/IG loader now handles JSON arrays (pretty-printed example
  files) as well as NDJSON and Bundles.

### Docs
- New: `docs/smart-scheduling-links.md`, `docs/provider-directory.md`,
  `docs/ci-and-deploys.md`. README, `atlas status`, roadmap, and
  known-limitations updated.

## [1.0.0] — 2026-06-12

Initial public release: FHIR R4/R5 patient population generator with 100+
clinical modules, US Core 6.1 builders, SDoH causal modeling, quality
MeasureReports, payer/claims, clinical notes, NDJSON/Parquet export, and the
`atlas generate` / `validate` / `report` / `serve` / `author` CLI.

[1.1.0]: https://github.com/ParkerApex/apex-atlas/releases/tag/v1.1.0
[1.0.0]: https://github.com/ParkerApex/apex-atlas/releases/tag/v1.0.0

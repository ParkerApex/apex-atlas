# Apex Atlas — Security & Data Provenance FAQ

*Last updated: 2026-06-12*

Answers for security reviewers, legal/compliance, and enterprise procurement.

## Does Atlas use data from QHINs, HIEs, Stedi, or CMS Blue Button?

**No.** Atlas does not connect to, ingest from, or replay records from Qualified Health Information Networks (QHIN/TEFCA), health information exchanges, Stedi, CMS Blue Button, or any production clinical or payer system.

**Yes — it maps to them.** Atlas generates FHIR that uses the same **resource types, US Core profiles, and workflow patterns** those channels deliver: clinical summaries (Patient, Condition, Encounter, MedicationRequest), payer artifacts (Coverage, Claim, ExplanationOfBenefit), bulk `$export`-style NDJSON, and quality MeasureReports. Cohort **statistics** (who has diabetes, how often they visit, whether they fill meds) mirror public US norms — so integration and AI pipelines see realistic panels, not empty conformance stubs.

## Is Apex Atlas data real patient data?

**No.** Every patient receives a Parker GPX identifier under the synthetic prefix (`GPX-SYN-…`). Records are generated from public statistical distributions and module rules. Atlas is **not** trained on, derived from, or informed by MIMIC, ePIC extracts, UK Biobank, or similar restricted sources.

## Could synthetic records be re-identified?

Atlas does not intentionally embed real identities. Residual re-identification risk depends on how you combine Atlas output with external data (employer files, small-area geography, etc.). Treat cohorts like any synthetic dataset: avoid linking to real keys without a separate risk assessment.

## Where do prevalence and clinical rates come from?

Each module declares `cites:` blocks pointing to CDC, NHANES, ACS, SEER, AHA, ACOG, BRFSS, and peer-reviewed literature. The [fidelity scorecard](./fidelity-scorecard.md) shows aggregate checks against those targets. See [known limitations](./known-limitations.md) for what “validated” does and does not mean.

## Does generation call external services?

| Feature | External calls? |
| --- | --- |
| `atlas generate` (default) | **No** — fully local and deterministic with a fixed seed. |
| `--notes-strategy llm` | **Yes** — Anthropic or OpenAI API (your key). |
| `atlas author research` | **Yes** — LLM + web search (your key). |
| `atlas serve` (hosted demo) | **No AI** for `/generate`; optional author CLI is separate. |

No telemetry or phone-home is built into the generator.

## What about PHI in logs?

The CLI and dev server do not upload bundles. If you enable LLM notes or author research, structured patient summaries are sent to **your** configured provider under **your** account. Review provider BAAs and data processing terms before using LLM features with sensitive workflows.

## Terminology licensing (SNOMED, LOINC, RxNorm, ICD-10)

Atlas emits standard codes in FHIR resources. Typical US research and integration testing falls under **UMLS Affiliate License** terms when accessing those code systems through normal channels. Atlas does not ship UMLS release files. **International use** may require separate SNOMED/LOINC agreements — assess per country.

## Is the code open source?

Dual-licensed:

- **Apache 2.0** — generator, modules, tooling (non-competing use).
- **Commercial license** — enterprise SLAs, indemnification, custom modules, competing platforms. See [COMMERCIAL.md](../COMMERCIAL.md).

## How are API keys handled?

- Read from environment (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`) or explicit CLI flags where supported.
- Never committed to the repo or baked into Docker images for `atlas serve`.
- Configure secrets via your platform (Fly, Render, Cloud Run) for hosted demos.

## `atlas serve` security model

The dev API has **no authentication, no rate limiting, and a 20,000-patient cap per request**. Suitable for demos behind a reverse proxy with rate limits and WAF — not a multi-tenant production service. See [deploy.md](./deploy.md).

## Supply chain

- Python package built with Hatchling; dependencies pinned in `pyproject.toml`.
- CI runs `pytest`, `ruff`, and `mypy` on changes.
- Pre-commit hooks available for contributors.

## Vulnerability reporting

Do **not** open public issues for security vulnerabilities. Email **security@parkerapex.com** — response within three business days.

## Audit artifacts

Each generation run writes `generation-metadata.json` (cohort id, seed, modules, feature flags, timestamps). Use it for internal governance and to reproduce cohorts.

## Commercial support

Enterprise indemnification, validated releases, and custom modules require a commercial agreement. Contact [licensing@parkerapex.com](mailto:licensing@parkerapex.com).

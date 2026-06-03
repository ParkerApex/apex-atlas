# Research-grounded module authoring — `atlas author`

This guide covers the `atlas author` command family: how to turn a cited
**research dossier** into a *draft* clinical module plus a matching *draft*
fidelity expectation, and how to promote a clinician-reviewed draft into the
bundled library.

It complements [`module_dsl.md`](./module_dsl.md) (the hand-authoring
reference). Where this guide and the loaders disagree, the code wins — the
relevant loaders are
[`modules/runtime.py`](../../src/parker_atlas/modules/runtime.py),
[`validation/expectations/__init__.py`](../../src/parker_atlas/validation/expectations/__init__.py),
and [`author/`](../../src/parker_atlas/author/).

---

## Why this exists

Atlas's edge over other synthetic-patient generators is **auditable, current
provenance**: every prevalence rate traces to a public source, and the cohort
fidelity harness checks output against those rates. The bottleneck on keeping
the library broad *and* current is authoring effort — exactly where competing
tools stall (libraries that plateau and go stale because authoring is hard).

`atlas author` closes that gap. It makes "draft a new module **with** its
sourced fidelity expectation" a single, auditable workflow, and it keeps a
human (clinician) in the loop as the gate before anything ships.

---

## The two-stage model

```
condition ──[research]──▶ <condition>.dossier.yaml ──[synthesize]──▶ draft module + draft expectation
            (Phase 2:        (cited, human-reviewable)              (round-tripped through the real loaders;
             web_search)                                            written to ./atlas-drafts/<condition>/)
                                                                                   │  clinician sign-off (SIGNOFF.md)
                                                                          [promote] ──▶ library/ + expectations/library/
```

- **The dossier is the artifact a clinician reviews.** It is structured and
  fully cited — every numeric claim carries a source.
- **Synthesis is deterministic** (no LLM). Given a dossier, the draft module
  and expectation are a pure function of it, so they are mechanically
  auditable and unit-tested. Both are round-tripped through the *real* runtime
  loaders, so a malformed dossier fails at author time — not at `atlas
  generate` / `atlas validate --cohort` time.
- **Drafts live outside the bundled library** (`./atlas-drafts/<condition>/`),
  so the runtime never loads unreviewed work. `atlas author promote` installs a
  reviewed draft into the shipping locations.

---

## Quick start

```bash
# 1. Produce a dossier (Phase 1: via the deep-research skill or by hand;
#    Phase 2: `atlas author research --condition glaucoma`).

# 2. Synthesize a draft module + expectation (both validated as they're built).
atlas author synthesize --dossier glaucoma.dossier.yaml --out ./atlas-drafts
# → ./atlas-drafts/glaucoma/{glaucoma.yaml, glaucoma.expectation.yaml, dossier.yaml, SIGNOFF.md}

# 3. Clinician reviews the draft and fills the `Signed-off-by:` line in SIGNOFF.md.

# 4. Promote into the bundled library (refuses to run while unsigned).
atlas author promote --draft ./atlas-drafts/glaucoma

# 5. Verify the loop closes: the module should validate against its own expectation.
atlas generate --module glaucoma --patients 5000 --seed 7 --out ./out
atlas validate --cohort --module glaucoma ./out
```

---

## The dossier schema

A dossier is one YAML file per condition. The loader
([`author/dossier.py`](../../src/parker_atlas/author/dossier.py)) enforces one
rule above all: **no uncited numbers**. Every numeric claim — the prevalence
cells, each observation `value_range`, each medication `fraction`, each
progression `probability` — must carry a `citation` with at least a `source`,
or the dossier fails to load. Structural FHIR validity (codes, `link_to`
wiring, bracket syntax) is checked during synthesis by the real loaders, not
duplicated here.

```yaml
condition: glaucoma                  # module name (snake_case)
version: 0.1.0
generated:                           # provenance of the research pass itself
  method: deep-research-skill        # deep-research-skill | web_search | manual
  model: claude-opus-4-8             # optional
  accessed: "2026-06-03"
codes:
  snomed: {system: http://snomed.info/sct, code: "23986001", display: "Glaucoma (disorder)"}
  icd10:
    - {code: "H40.9", display: "Unspecified glaucoma"}
prevalence:
  stratify_by: age_bracket           # age_bracket | sex_and_age
  cells:                             # {bracket: rate}  — or {female:{…}, male:{…}} for sex_and_age
    "0-39": 0.001
    "40-59": 0.012
    "60-99": 0.040
  citation: {source: "Friedman DS et al. Arch Ophthalmol 2004", url: "…", table: "Table 2", accessed: "2026-06-03", summary: "…"}
onset_age: {min: 40, max: 80}        # required (progression/timing is measured from onset)
clinical:
  encounters:
    - spec_id: glaucoma_eye_visit
      class: AMB
      type: {system: http://snomed.info/sct, code: "185349003", display: "Encounter for check up"}
      reason: {system: http://snomed.info/sct, code: "23986001", display: "Glaucoma"}   # optional
  observations:
    - spec_id: glaucoma_iop
      category: laboratory           # MUST be one the generator supports: vital-signs | laboratory
      link_to: glaucoma_eye_visit    # optional; must name an encounter spec_id above
      loinc: {system: http://loinc.org, code: "79892-9", display: "Intraocular pressure of Eye"}
      value_range: {low: 22, high: 32, precision: 0}
      unit: mm[Hg]
      unit_code: mm[Hg]              # optional
      citation: {source: "AAO POAG PPP 2020", url: "…", summary: "…"}
  medications:
    - spec_id: glaucoma_latanoprost
      medication: {system: http://www.nlm.nih.gov/research/umls/rxnorm, code: "28809", display: "latanoprost"}
      fraction: 0.70                 # share of positive patients who receive it → emit probability
      link_to: glaucoma_eye_visit    # optional
      citation: {source: "AAO POAG PPP 2020", url: "…", summary: "…"}
progressions:                        # optional one-hop progressions
  - {to: "module:condition", after_years: 5, probability: 0.03, citation: {source: "…", url: "…"}}
notes: "Free-text reviewer guidance / caveats."
```

### How the dossier maps to the draft module

| Dossier | Module |
|---|---|
| `codes.snomed` | the condition `code` |
| `prevalence.cells` | the condition `prevalence` (age- or sex-stratified) |
| `onset_age` | the condition `onset_age` |
| `clinical.encounters` | `Encounter` emits (`when: onset`) |
| `clinical.observations` | `Observation` emits (`value_range`, `unit`, `link_to`) |
| `clinical.medications` | `MedicationRequest` emits, `fraction` → `probability` |
| `progressions` | the condition `progressions` |
| all `citation`s (deduped) | the module `cites:` block |

### How the dossier maps to the draft expectation

The prevalence cells become a `conditional_prevalence` metric with a Wilson
tolerance at 99% confidence, and `source.provenance: sourced` — the precise
guarantee a research pass provides (cited, but not independently re-verified
against microdata by the project). After promotion you can upgrade a module to
`verified` by re-computing the rate from public microdata.

---

## The sign-off gate

`atlas author synthesize` writes a `SIGNOFF.md` checklist into the draft
directory. `atlas author promote` refuses to install the module until a
reviewer fills in a non-empty value on the `Signed-off-by:` line (override with
`--force`, which is not recommended). This keeps a licensed clinician as the
required gate between "auto-drafted" and "shipped" — drafts carry a `# DRAFT`
banner that promotion strips.

---

## Phase 2 — autonomous research (`atlas author research`)

`atlas author research --condition <name>` is currently a stub. When the
in-package, `web_search`-backed backend ships, it will fetch live sources and
emit a dossier against the schema above autonomously; until then, produce the
dossier with the `deep-research` skill or by hand and run `atlas author
synthesize`. The dossier contract is identical either way, so nothing
downstream changes when the backend lands.

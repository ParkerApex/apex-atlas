# Module Authoring Guide — the APEX Atlas DSL

This is the authoritative reference for the YAML module DSL. It is written
against the loader in
[`src/parker_atlas/modules/runtime.py`](../../src/parker_atlas/modules/runtime.py)
and is kept in sync with it — where this guide and the code disagree, the code
wins (and that's a bug in this doc; please file it).

A **module** is a self-contained clinical pathway: one YAML file that declares a
set of **conditions**, the **clinical resources** each condition emits when a
patient has it, and optional **progressions** to downstream conditions over
time. The generator loads modules, runs each patient through them, and produces
FHIR resources.

The canonical worked example referenced throughout is
[`library/diabetes.yaml`](../../src/parker_atlas/modules/library/diabetes.yaml)
and its overlay
[`library/diabetes.progressions.yaml`](../../src/parker_atlas/modules/library/diabetes.progressions.yaml).

---

## The execution model (read this first)

Atlas modules are **probability modules**, not full state machines. Understanding
the model up front saves you from designing things the DSL can't express:

- **Each condition is a single Bernoulli trial.** For a given patient the
  generator looks up the condition's prevalence for that patient's age (and
  optionally sex), draws once, and the condition either fires or it doesn't.
  There are no intermediate states, no transitions, no per-visit loops.
- **The only multi-step mechanism is a one-hop progression.** A condition that
  fired can progress to *one* downstream condition after N years. Progressions
  do **not** chain — a progressed condition does not itself progress further.
- **Timing is nominal, not calendar-exact.** Everywhere the DSL does date math,
  a month is 30 days and a year is 365 days. There is no leap-year/calendar
  arithmetic.
- **Value distributions are uniform only.** An emitted lab/vital value is drawn
  uniformly between a `low` and `high`. There is no mean/stddev or other
  distribution.

If your clinical model needs richer dynamics, model it as several conditions
wired together with `requires` and `progressions` rather than reaching for a
state machine.

---

## Quick start

### 1. Write a minimal module

Save this as `src/parker_atlas/modules/library/hello_htn.yaml`:

```yaml
module: hello_htn
version: 0.1.0
description: Minimal example — essential hypertension by age band.
cites:
  - source: Example source (replace before merge)
    url: https://example.org
    summary: Placeholder prevalence for demonstration only.
conditions:
  - id: essential_hypertension
    code:
      system: http://snomed.info/sct
      code: "59621000"
      display: Essential hypertension (disorder)
    prevalence:
      "0-17": 0.0
      "18-39": 0.08
      "40-59": 0.33
      "60-99": 0.63
    onset_age:
      min: 30
      max: 75
    emits:
      - resource_type: Encounter
        spec_id: htn_visit
        when: onset
        encounter_class: AMB
        type:
          system: http://snomed.info/sct
          code: "185349003"
          display: Encounter for check up
      - resource_type: Observation
        spec_id: htn_systolic
        when: onset
        link_to: htn_visit
        category: vital-signs
        code:
          system: http://loinc.org
          code: "8480-6"
          display: Systolic blood pressure
        value_range: {low: 140, high: 180, precision: 0}
        unit: mm[Hg]
        unit_code: mm[Hg]
```

### 2. Inspect and run it

Modules are loaded **by name** from the bundled library directory; there is no
flag to load a module from an arbitrary path. So once the file is in
`src/parker_atlas/modules/library/`, reference it by its `module:` name:

```bash
atlas modules --list                 # your module should appear
atlas modules --show hello_htn       # renders the parsed structure
atlas generate --module hello_htn --patients 100 --seed 1 --out ./out --summary
```

`atlas modules --show` parses the file through the same loader the generator
uses, so it's the fastest way to surface a `ModuleError` while iterating. A bad
module fails loudly with a message pointing at the offending field (see
[Validation & common errors](#validation--common-errors)).

### 3. Add fidelity expectations (recommended)

The cohort fidelity harness checks that aggregate synthetic output matches your
cited rates. Add a matching expectation library under
[`src/parker_atlas/validation/expectations/library/`](../../src/parker_atlas/validation/expectations/library/)
and run:

```bash
atlas validate --cohort --module hello_htn --patients 5000 --seed 1
```

---

## Module file anatomy

### Top-level keys

| Key | Required | Type | Default | Notes |
|-----|----------|------|---------|-------|
| `module` | **yes** | string | — | The module's name. Used to load it (`--module <name>`) and to namespace cross-module references. |
| `version` | **yes** | string | — | Free-form (convention: semver). Not validated. |
| `conditions` | **yes** | list | — | One or more condition definitions. |
| `description` | no | string | `""` | Human-readable summary. Use YAML block scalars (`>`) for prose. |
| `cites` | no | list | none | Source citations — see [Citations](#citations-cites). |

> There is **no** top-level `emits`, `progressions`, `requires`, or `mortality`
> key. Those all live **inside individual conditions**. Unknown top-level keys
> are silently ignored (with one exception: malformed `cites` entries raise a
> hard error).

### Citations (`cites`)

Each entry must have exactly `source` and `url`; `summary` is optional. Unlike
the rest of the DSL, **unknown keys here raise an error**, so keep entries to
these three fields:

```yaml
cites:
  - source: NCHS Data Brief 516 (NHANES Aug 2021–Aug 2023)
    url: https://www.cdc.gov/nchs/products/databriefs/db516.htm
    summary: >
      US adults 20+ total diabetes prevalence: 3.6% at 20-39, 17.7% at
      40-59, 27.3% at 60+.
```

Every prevalence and progression rate you ship must trace to a public,
redistributable source. See the [Authoring checklist](#authoring-checklist).

---

## Conditions

A condition is one diagnosable entity. Fields:

| Field | Required | Type | Default | Notes |
|-------|----------|------|---------|-------|
| `id` | **yes** | string | — | Unique within the module. Used by `requires`, progression targets, and emits. |
| `code` | **yes** | mapping | — | The diagnosis coding (`system` / `code` / `display`). |
| `prevalence` | no | mapping | `{}` | Age- (and optionally sex-) stratified Bernoulli rates. Omit/empty ⇒ the condition can only be reached via a progression. |
| `onset_age` | no | mapping | none | `{min, max}` in years. Required if the condition has `progressions` or `mortality`. |
| `requires` | no | string or list | none | Gating dependencies — see [requires](#requires--cross-module-dependencies). |
| `emits` | no | list | none | Resources produced when the condition fires. |
| `progressions` | no | list | none | One-hop transitions to downstream conditions. |
| `mortality` | no | mapping | none | Optional death model — see [Mortality](#mortality). |

`id` and `code` are genuinely mandatory — omitting them raises a raw
`KeyError`/`TypeError` rather than a friendly message, so always include both.

### The `code` mapping

Every coding in the DSL (`code`, `type`, `reason`, `medication`, `vaccine`,
`cause`, etc.) has exactly three required fields:

```yaml
code:
  system: http://snomed.info/sct        # terminology system URL
  code: "73211009"                       # quote numeric codes so YAML keeps them strings
  display: Diabetes mellitus (disorder)
```

Common systems: `http://snomed.info/sct` (conditions, procedures),
`http://loinc.org` (observations), `http://www.nlm.nih.gov/research/umls/rxnorm`
(medications), `http://hl7.org/fhir/sid/cvx` (vaccines). **Always quote numeric
codes** — an unquoted `73211009` is fine, but codes like `4548-4` or those with
leading zeros must be strings.

---

## Prevalence & onset

### Prevalence

Prevalence is a map of **age brackets** to rates in `[0, 1]`. Brackets are
written `"LOW-HIGH"` and are **inclusive on both ends**. Quote them so YAML
doesn't parse them as numbers.

**Flat (age-only):**

```yaml
prevalence:
  "0-19": 0.003
  "20-39": 0.036
  "40-59": 0.177
  "60-99": 0.273
```

**Sex-stratified** — use *only* the keys `female` and `male` at the top level,
each holding its own bracket map. Any other key alongside them is rejected:

```yaml
prevalence:
  female:
    "0-39": 0.05
    "40-99": 0.20
  male:
    "0-39": 0.07
    "40-99": 0.26
```

Bracket lookup semantics:

- **First match wins.** Overlapping brackets are not detected; order them so the
  first containing the patient's age is the one you want.
- **Gaps are allowed.** If no bracket contains the age, the condition is simply
  skipped for that patient (no error). A `female`-only map never fires for male
  patients.
- A condition reachable **only via progression** should declare
  `prevalence: {"0-99": 0.0}` so the direct trial can never fire it (see
  `diabetic_ckd` in diabetes.yaml).

### Onset (`onset_age`)

```yaml
onset_age:
  min: 35
  max: 70
```

When set, a fired condition gets an `onset_date`:

- The onset age is drawn uniformly in `[min, min(max, current_age)]`.
- If the patient is younger than `min`, onset is **today** ("just diagnosed").
- `onset_date = today − (current_age − onset_age) years` (365-day years).

`onset_age` is **required** for any condition that declares `progressions` or
`mortality`, since both are measured forward from onset. Without `onset_age` the
condition still fires, but emits anchored to `onset` fall back to `today`.

---

## Emits

`emits` is a list of clinical resources produced when the condition fires. Atlas
supports **seven** resource types:

`Encounter`, `Observation`, `MedicationRequest`, `Procedure`,
`AllergyIntolerance`, `Immunization`, `DiagnosticReport`.

### Fields common to every emit

| Field | Required | Default | Notes |
|-------|----------|---------|-------|
| `resource_type` | **yes** | — | One of the seven above. |
| `spec_id` | **yes** | — | Identifier unique within the condition. Used by `link_to` and DiagnosticReport `results`. |
| `probability` | no | `1.0` | Per-emit chance in `[0, 1]`. Drawn independently of the condition and of other emits. |
| `when` | no | `today` | Timing anchor + optional offset — see below. |
| `link_to` | no | none | (Most types) the `spec_id` of an `Encounter` **in the same condition** to attach this resource to. |

### The `when` grammar

```
when := ("today" | "onset") ( ("+"|"-") <digits> ("d"|"w"|"m"|"y") )?
```

- **Anchors:** `today` (the simulation date) or `onset` (the condition's onset
  date; falls back to `today` if the condition has no `onset_age`).
- **Offset units:** `d` = 1 day, `w` = 7 days, `m` = 30 days, `y` = 365 days.
- **One offset only** — `onset+1y+30d` is *not* valid.

Valid: `today`, `onset`, `onset+30d`, `onset+90d`, `onset+6m`, `today-1y`,
`today-2w`. Anything else raises a `ModuleError`.

### Encounter

Encounters are the anchor other resources link to. They take no `link_to`.

```yaml
- resource_type: Encounter
  spec_id: diabetes_diagnosis_visit
  when: onset
  encounter_class: AMB            # conventionally AMB | IMP | EMER | HH | VR (not enum-checked)
  type:
    system: http://snomed.info/sct
    code: "185349003"
    display: Encounter for check up
  reason:                          # optional
    system: http://snomed.info/sct
    code: "73211009"
    display: Diabetes mellitus
```

| Field | Required | Notes |
|-------|----------|-------|
| `encounter_class` | **yes** | Free string; convention `AMB`/`IMP`/`EMER`/`HH`/`VR`. |
| `type` | **yes** | Coding. |
| `reason` | no | Coding. |

### Observation

Declare **exactly one** of `value_range` (single value) or `components`
(multi-component panel) — not both, not neither.

Single-value form (`unit` is required here):

```yaml
- resource_type: Observation
  spec_id: diabetes_initial_a1c
  when: onset
  link_to: diabetes_diagnosis_visit
  category: laboratory             # conventionally "laboratory" | "vital-signs"
  code:
    system: http://loinc.org
    code: "4548-4"
    display: Hemoglobin A1c/Hemoglobin.total in Blood
  value_range:
    low: 7.5
    high: 11.0
    precision: 1                   # decimal places; 0 ⇒ integer. default 1
  unit: "%"
  unit_code: "%"                   # optional; defaults to `unit`
```

Multi-component form (e.g. a blood-pressure panel) — each component carries its
own `code`, `value_range`, and `unit`:

```yaml
- resource_type: Observation
  spec_id: bp_panel
  when: onset
  link_to: htn_visit
  category: vital-signs
  code:
    system: http://loinc.org
    code: "85354-9"
    display: Blood pressure panel
  components:
    - code: {system: http://loinc.org, code: "8480-6", display: Systolic blood pressure}
      value_range: {low: 140, high: 180, precision: 0}
      unit: mm[Hg]
    - code: {system: http://loinc.org, code: "8462-4", display: Diastolic blood pressure}
      value_range: {low: 90, high: 110, precision: 0}
      unit: mm[Hg]
```

`value_range` requires `low` and `high` (with `high >= low`); `precision`
defaults to `1` and `0` yields an integer.

### MedicationRequest

```yaml
- resource_type: MedicationRequest
  spec_id: diabetes_metformin
  when: onset
  link_to: diabetes_diagnosis_visit
  probability: 0.70                # only ~70% of diagnosed patients get this
  medication:
    system: http://www.nlm.nih.gov/research/umls/rxnorm
    code: "860975"
    display: Metformin 500 MG Oral Tablet
  reason:                          # optional Coding
    system: http://snomed.info/sct
    code: "73211009"
    display: Diabetes mellitus
```

### Procedure

```yaml
- resource_type: Procedure
  spec_id: cabg
  when: onset+14d
  link_to: cardiac_admission
  code:                            # SNOMED CT procedure
    system: http://snomed.info/sct
    code: "232717009"
    display: Coronary artery bypass graft
  reason:                          # optional
    system: http://snomed.info/sct
    code: "414545008"
    display: Ischemic heart disease
```

### AllergyIntolerance

```yaml
- resource_type: AllergyIntolerance
  spec_id: penicillin_allergy
  code:
    system: http://snomed.info/sct
    code: "373270004"
    display: Penicillin allergy
  category: medication             # optional, default "medication"
  criticality: high               # optional, default "low"
  reaction:                        # optional Coding (manifestation)
    system: http://snomed.info/sct
    code: "247472004"
    display: Hives
```

AllergyIntolerance takes no `link_to`.

### Immunization

```yaml
- resource_type: Immunization
  spec_id: flu_shot
  when: today
  link_to: wellness_visit
  vaccine:
    system: http://hl7.org/fhir/sid/cvx
    code: "140"
    display: Influenza, seasonal, injectable
```

### DiagnosticReport

A DiagnosticReport bundles Observations. Its `results` list references
`spec_id`s of `Observation` emits **in the same condition** (each must exist),
and must be non-empty.

```yaml
- resource_type: DiagnosticReport
  spec_id: lipid_panel_report
  when: onset
  link_to: lipid_visit
  code:
    system: http://loinc.org
    code: "57698-3"
    display: Lipid panel with direct LDL
  results:
    - ldl_observation
    - hdl_observation
  conclusion: Elevated LDL consistent with hypercholesterolemia.   # optional
```

### Linking emits together

- `link_to` attaches an Observation / MedicationRequest / Procedure /
  Immunization / DiagnosticReport to an `Encounter` **in the same condition**. A
  `link_to` that doesn't match an Encounter `spec_id` is a `ModuleError`.
- DiagnosticReport `results` must reference real Observation `spec_id`s in the
  same condition.
- Each emit's `probability` is evaluated independently — a linked Observation can
  fire even if you set a low probability on its Encounter, so keep encounters at
  the default `1.0` unless you mean otherwise.

---

## `requires` / cross-module dependencies

`requires` gates a condition on other conditions already having fired. It accepts
a single string or a list, and supports two reference forms:

```yaml
# sibling (same module) — must be declared EARLIER in this file
requires: prediabetes

# cross-module — "<module_name>:<condition_id>"
requires: hypertension:essential_hypertension

# multiple (AND logic — all must be satisfied)
requires:
  - hypertension:essential_hypertension
  - diabetes:diabetes_mellitus
```

Rules:

- **Sibling references must point to an earlier-declared condition** in the same
  module (forward references and self-references are rejected). Declaration order
  is significant.
- **Cross-module references** (`module:cond`) are resolved at run time against
  the set of conditions that fired in modules run earlier in the same invocation.
  Run the upstream module first:
  `atlas generate --module hypertension,complications`.
- A gated condition is skipped entirely (no prevalence trial) unless **all** its
  dependencies are satisfied.

See [`library/complications.yaml`](../../src/parker_atlas/modules/library/complications.yaml)
for a worked cross-module example.

---

## Progressions

A progression moves a patient from a fired source condition to a downstream
target condition after a number of years. Progressions are declared **inline on
the source condition** (which must have an `onset_age`):

```yaml
conditions:
  - id: diabetes_mellitus
    # ...
    onset_age: {min: 35, max: 70}
    progressions:
      - to: diabetic_ckd            # sibling id, or "<module>:<cond>" cross-module
        after_years: 10
        probability: 0.20
      - to: diabetic_retinopathy
        after_years: 10
        probability: 0.30
```

Each progression needs `to`, `after_years`, and `probability` (in `[0, 1]`).
There is **no `from`** on inline progressions — the source is the condition the
block sits on — and **no `when`/offset**; timing is purely `after_years` from the
source's onset.

Execution semantics:

- A progression only fires if the source fired **and** has an `onset_date`, the
  target hasn't already fired on its own, and the projected date
  (`onset_date + after_years`) is not in the future.
- **One hop only.** A progressed condition does not itself progress further.
- Progression targets should set `prevalence: {"0-99": 0.0}` so they can be
  reached *only* via progression, never by a direct trial.
- `to` may be a sibling id or a cross-module `module:cond` reference (the target
  module must be active in the same run).

### Progression overlays (`<name>.progressions.yaml`)

Inline progression rates are the **fallback**. A sibling file named
`<module>.progressions.yaml` (same directory) is auto-applied at load time and
**overrides the rates** of progressions already declared in the base module. The
naming convention is load-bearing, and overlay files do not appear in
`atlas modules --list` — they are not standalone modules.

```yaml
module: diabetes                    # must match the base module name
version: 1.1.0
source:
  name: KDIGO 2024 / USRDS 2023 / UKPDS 64 (CKD); Yau 2012 (DR)
  provenance: sourced               # must be exactly "sourced" or "verified"
  url: https://kdigo.org/guidelines/ckd-evaluation-and-management/
  citations:                        # free-form; mirror your cites entries
    - source: "Adler AI et al. UKPDS 64. Kidney International. 2003;63(1):225-232."
      url: https://doi.org/10.1046/j.1523-1755.2003.00712.x
progressions:
  - from: diabetes_mellitus         # overlays use explicit from + to
    to: diabetic_ckd
    after_years: 10
    probability: 0.2
  - from: diabetes_mellitus
    to: diabetic_retinopathy
    after_years: 10
    probability: 0.3
```

Overlay rules:

- `module` must equal the base module's name.
- `source.provenance` must be exactly `sourced` or `verified`.
- Each entry needs `from`, `to`, `after_years`, `probability`.
- **Overlays can only override existing `(from, to)` pairs** — they cannot add a
  progression that the base module didn't declare.

The intended workflow: hand-author the base module with placeholder rates inline,
then generate the sourced overlay from real data with
`atlas ingest progression`, which writes the `<name>.progressions.yaml` for you.

---

## Mortality

A condition may carry an optional death model. It requires `onset_age` on the
condition (mortality is measured forward from onset). The runtime parses and
validates this; the generator applies it after diagnoses are known.

```yaml
mortality:
  probability: 0.15        # required, in [0, 1]
  after_years: 5           # optional, default 0; years from onset
  cause:                   # optional Coding
    system: http://snomed.info/sct
    code: "22298006"
    display: Myocardial infarction
```

---

## Validation & common errors

The loader validates aggressively and raises `ModuleError` with a message that
names the offending field. Surface errors fast with
`atlas modules --show <name>`. The most common ones:

| Message contains | Cause |
|------------------|-------|
| `missing required key: <module/version/conditions>` | A top-level key is absent. |
| `duplicate condition id` | Two conditions share an `id`. |
| `invalid bracket ...; expected 'LOW-HIGH'` | A prevalence key isn't `"<int>-<int>"`. |
| `sex-stratified prevalence keys must be in ['female', 'male']` | A non-`female`/`male` key sits alongside them. |
| `must declare exactly one of value_range ... or components` | An Observation has both or neither. |
| `unit` (missing) | A single-value Observation omitted `unit`. |
| `unsupported resource_type` | `resource_type` isn't one of the seven. |
| `duplicate emit spec_ids` | Two emits in one condition share a `spec_id`. |
| `link_to=... does not match any Encounter spec_id` | `link_to` points at a non-Encounter or unknown spec_id. |
| `references unknown Observation spec_id(s)` | DiagnosticReport `results` names a missing Observation. |
| `when=... not supported` | The `when` string doesn't match the grammar. |
| `requires=... must reference an earlier-declared sibling` | A sibling `requires` points forward or at an unknown id. |
| `progressions require an onset_age` | A condition has `progressions` but no `onset_age`. |
| `overlay declares (from, to) pairs not present in module` | An overlay tried to add a new progression. |
| `must declare source.provenance of 'sourced' or 'verified'` | An overlay's `source.provenance` is wrong. |

Note: unknown keys at the module/condition/emit level are **silently ignored**
(only `cites` and `code`-style mappings reject extras). A typo'd field name won't
error — it just won't take effect. Double-check field names against this guide.

---

## Authoring checklist

Before opening a PR, especially for a clinical module:

- [ ] Every prevalence, incidence, and progression rate cites a **public,
      redistributable** source (`cites`, and `source` in any overlay). No
      credentialed datasets (MIMIC, UK Biobank, etc.).
- [ ] Progression overlays declare `source.provenance: sourced` (or `verified`).
- [ ] Codes use the appropriate terminology system and numeric codes are quoted.
- [ ] `atlas modules --show <name>` loads without error.
- [ ] `atlas generate --module <name> --seed 1 --summary` produces plausible
      prevalence.
- [ ] A fidelity expectation library exists under
      [`validation/expectations/library/`](../../src/parker_atlas/validation/expectations/library/)
      and `atlas validate --cohort --module <name>` passes within tolerance.
- [ ] Conflicts of interest (industry affiliation, consulting) are disclosed in
      the module header `description`, per
      [CONTRIBUTING.md](../../CONTRIBUTING.md).
- [ ] If LLM-assisted, a clinician has reviewed and signed off before merge.

---

## What the DSL does *not* support

So you don't design against it:

- No state machines, intermediate states, or multi-hop progression chains.
- No `from` or `when`/offset on inline progressions (only `after_years`).
- No non-uniform value distributions (uniform `low`–`high` only).
- No calendar-accurate dates (month = 30 days, year = 365 days throughout).
- No mutually-exclusive / conflict gating (`requires` is positive AND-logic only).
- No enum validation on `encounter_class`, Observation `category`, or allergy
  `category`/`criticality` — follow the documented conventions.
- No top-level `requires` / `emits` / `progressions` / `mortality` — all are
  per-condition.
- No loading a module from an arbitrary path — modules live in the bundled
  library directory and are referenced by name.

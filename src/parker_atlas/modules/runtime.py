"""
Clinical module runtime — probability-module flavor.

Parker Atlas modules are authored in YAML. The minimal flavor supported
today is a **probability module**: each condition carries an age-bracketed
(optionally sex-stratified) prevalence. For each patient, each condition
is a Bernoulli trial against its bracket-specific rate.

This is deliberately simpler than the state-machine DSL described in
`docs/architecture.md`. State machines (onset timing, progression,
resolution, medication cascades) land in a later milestone; the
probability flavor is the floor, not the ceiling.

Module YAML shape:
    module: <name>
    version: <semver>
    description: <str>
    cites:
      - source: <str>
        url: <str>
        summary: <str>
    conditions:
      - id: <short_identifier>
        code:
          system: <terminology-system-url>
          code: <terminology-code>
          display: <human-readable>
        prevalence:
          "0-17": 0.04
          "18-34": 0.22
          ...
          # Optionally sex-stratified:
          # female:
          #   "0-17": 0.03
          #   ...
          # male:
          #   "0-17": 0.05
          #   ...
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, timedelta
from importlib import resources
from typing import Any

import yaml


@dataclass(frozen=True, slots=True)
class Coding:
    system: str
    code: str
    display: str


@dataclass(frozen=True, slots=True)
class Citation:
    source: str
    url: str
    summary: str = ""


@dataclass(frozen=True, slots=True)
class ValueRange:
    """Uniform-sample range for an Observation value."""

    low: float
    high: float
    precision: int = 1  # decimal places to round to; 0 → integer


@dataclass(frozen=True, slots=True)
class ObservationComponentEmit:
    code: Coding
    value_range: ValueRange
    unit: str
    unit_code: str | None = None  # defaults to unit


# Allowed `when` values on emits. "today" → simulation reference date.
# "onset" → the diagnosis's sampled onset_date (falls back to today if
# the condition has no onset_age).
ALLOWED_EMIT_WHEN = ("today", "onset")


@dataclass(frozen=True, slots=True)
class EncounterEmit:
    spec_id: str
    encounter_class: str  # AMB, IMP, EMER, HH, VR
    type_code: Coding
    reason_code: Coding | None = None
    probability: float = 1.0
    when: str = "today"


@dataclass(frozen=True, slots=True)
class ObservationEmit:
    spec_id: str
    category: str  # "vital-signs" | "laboratory"
    code: Coding
    # Single-value OR multi-component. Enforced at parse time.
    value_range: ValueRange | None = None
    unit: str | None = None
    unit_code: str | None = None
    components: tuple[ObservationComponentEmit, ...] = ()
    probability: float = 1.0
    when: str = "today"


@dataclass(frozen=True, slots=True)
class MedicationRequestEmit:
    spec_id: str
    medication_code: Coding
    reason_code: Coding | None = None
    probability: float = 1.0
    when: str = "today"


EmitSpec = EncounterEmit | ObservationEmit | MedicationRequestEmit


@dataclass(frozen=True, slots=True)
class OnsetAgeRange:
    """Patient age (years) at which a condition typically presents."""

    min: int
    max: int


@dataclass(frozen=True, slots=True)
class ConditionSpec:
    """One condition a module can assign to a patient."""

    id: str
    code: Coding
    # Bracket key is (age_low, age_high) inclusive. Optional sex stratification
    # keys the outer dict by "female" | "male"; None means the inner dict is
    # used for all sexes.
    prevalence_by_bracket: dict[tuple[int, int], float]
    prevalence_by_sex: dict[str, dict[tuple[int, int], float]] | None = None
    # Additional resources emitted when the condition fires for a patient.
    emits: tuple[EmitSpec, ...] = ()
    # If set, runtime samples a per-patient onset age and computes a
    # Condition.onsetDateTime relative to the simulation's reference date.
    onset_age: OnsetAgeRange | None = None


@dataclass(frozen=True, slots=True)
class Module:
    name: str
    version: str
    description: str
    cites: tuple[Citation, ...]
    conditions: tuple[ConditionSpec, ...]


# ---- Concrete per-patient sampled resources -------------------------------


@dataclass(frozen=True, slots=True)
class SampledComponent:
    code: Coding
    value: float
    unit: str
    unit_code: str


@dataclass(frozen=True, slots=True)
class SampledEncounter:
    spec_id: str
    encounter_class: str
    type_code: Coding
    reason_code: Coding | None
    effective_date: date
    when: str  # "today" | "onset"


@dataclass(frozen=True, slots=True)
class SampledObservation:
    spec_id: str
    category: str
    code: Coding
    value: float | None
    unit: str | None
    unit_code: str | None
    components: tuple[SampledComponent, ...]
    effective_date: date
    when: str


@dataclass(frozen=True, slots=True)
class SampledMedicationRequest:
    spec_id: str
    medication_code: Coding
    reason_code: Coding | None
    effective_date: date
    when: str


SampledResource = SampledEncounter | SampledObservation | SampledMedicationRequest


@dataclass(frozen=True, slots=True)
class Diagnosis:
    """Output of run_module: a condition the module says this patient has."""

    condition: ConditionSpec
    sampled_resources: tuple[SampledResource, ...] = ()
    # Date the condition is recorded as having begun for this patient.
    # None means the module did not declare an onset_age range; the FHIR
    # Condition will be emitted without onsetDateTime in that case.
    onset_date: date | None = None


class ModuleError(ValueError):
    """Raised when a module file cannot be parsed or validated."""


# -- Parsing -----------------------------------------------------------------


def _parse_bracket(s: str) -> tuple[int, int]:
    try:
        lo_str, hi_str = s.split("-")
        return int(lo_str), int(hi_str)
    except ValueError as exc:
        raise ModuleError(f"invalid bracket {s!r}; expected 'LOW-HIGH'") from exc


def _parse_prevalence(
    raw: dict[str, Any],
) -> tuple[
    dict[tuple[int, int], float],
    dict[str, dict[tuple[int, int], float]] | None,
]:
    sex_keys = {"female", "male"}
    if set(raw.keys()) & sex_keys:
        # Sex-stratified form.
        by_sex: dict[str, dict[tuple[int, int], float]] = {}
        for sex, brackets in raw.items():
            if sex not in sex_keys:
                raise ModuleError(
                    f"sex-stratified prevalence keys must be in {sorted(sex_keys)}, "
                    f"got {sex!r}"
                )
            by_sex[sex] = {_parse_bracket(k): float(v) for k, v in brackets.items()}
        return {}, by_sex
    flat = {_parse_bracket(k): float(v) for k, v in raw.items()}
    return flat, None


def _parse_coding(raw: dict[str, Any], context: str) -> Coding:
    try:
        return Coding(**raw)
    except TypeError as exc:
        raise ModuleError(f"{context}: malformed code {raw!r}: {exc}") from exc


def _parse_value_range(raw: dict[str, Any], context: str) -> ValueRange:
    for required in ("low", "high"):
        if required not in raw:
            raise ModuleError(f"{context}: value_range missing {required!r}")
    precision = int(raw.get("precision", 1))
    if precision < 0:
        raise ModuleError(f"{context}: value_range.precision must be >= 0")
    low = float(raw["low"])
    high = float(raw["high"])
    if high < low:
        raise ModuleError(f"{context}: value_range.high {high} < low {low}")
    return ValueRange(low=low, high=high, precision=precision)


def _parse_probability(raw: dict[str, Any], context: str) -> float:
    p = float(raw.get("probability", 1.0))
    if not 0.0 <= p <= 1.0:
        raise ModuleError(f"{context}: probability {p} must be in [0, 1]")
    return p


def _parse_when(raw: dict[str, Any], context: str) -> str:
    when = str(raw.get("when", "today"))
    if when not in ALLOWED_EMIT_WHEN:
        raise ModuleError(
            f"{context}: when={when!r} not supported; "
            f"choices: {list(ALLOWED_EMIT_WHEN)}"
        )
    return when


def _parse_observation_component(raw: dict[str, Any], ctx: str) -> ObservationComponentEmit:
    for req in ("code", "value_range", "unit"):
        if req not in raw:
            raise ModuleError(f"{ctx}: component missing {req!r}")
    return ObservationComponentEmit(
        code=_parse_coding(raw["code"], f"{ctx}.code"),
        value_range=_parse_value_range(raw["value_range"], f"{ctx}.value_range"),
        unit=str(raw["unit"]),
        unit_code=str(raw["unit_code"]) if raw.get("unit_code") else None,
    )


def _parse_observation_emit(raw: dict[str, Any], ctx: str) -> ObservationEmit:
    for req in ("spec_id", "category", "code"):
        if req not in raw:
            raise ModuleError(f"{ctx}: Observation emit missing {req!r}")
    components_raw = raw.get("components") or ()
    has_value = "value_range" in raw
    if bool(components_raw) == has_value:
        raise ModuleError(
            f"{ctx}: Observation emit must declare exactly one of "
            f"`value_range` (single-value) or `components` (multi-component)"
        )
    components = tuple(
        _parse_observation_component(c, f"{ctx}.components[{i}]")
        for i, c in enumerate(components_raw)
    )
    value_range = (
        _parse_value_range(raw["value_range"], f"{ctx}.value_range") if has_value else None
    )
    if has_value and "unit" not in raw:
        raise ModuleError(f"{ctx}: Observation emit with value_range must declare `unit`")
    return ObservationEmit(
        spec_id=str(raw["spec_id"]),
        category=str(raw["category"]),
        code=_parse_coding(raw["code"], f"{ctx}.code"),
        value_range=value_range,
        unit=str(raw["unit"]) if has_value else None,
        unit_code=str(raw["unit_code"]) if has_value and raw.get("unit_code") else None,
        components=components,
        probability=_parse_probability(raw, ctx),
        when=_parse_when(raw, ctx),
    )


def _parse_encounter_emit(raw: dict[str, Any], ctx: str) -> EncounterEmit:
    for req in ("spec_id", "encounter_class", "type"):
        if req not in raw:
            raise ModuleError(f"{ctx}: Encounter emit missing {req!r}")
    reason = raw.get("reason")
    return EncounterEmit(
        spec_id=str(raw["spec_id"]),
        encounter_class=str(raw["encounter_class"]),
        type_code=_parse_coding(raw["type"], f"{ctx}.type"),
        reason_code=_parse_coding(reason, f"{ctx}.reason") if reason else None,
        probability=_parse_probability(raw, ctx),
        when=_parse_when(raw, ctx),
    )


def _parse_medication_request_emit(raw: dict[str, Any], ctx: str) -> MedicationRequestEmit:
    for req in ("spec_id", "medication"):
        if req not in raw:
            raise ModuleError(f"{ctx}: MedicationRequest emit missing {req!r}")
    reason = raw.get("reason")
    return MedicationRequestEmit(
        spec_id=str(raw["spec_id"]),
        medication_code=_parse_coding(raw["medication"], f"{ctx}.medication"),
        reason_code=_parse_coding(reason, f"{ctx}.reason") if reason else None,
        probability=_parse_probability(raw, ctx),
        when=_parse_when(raw, ctx),
    )


def _parse_emit(raw: dict[str, Any], ctx: str) -> EmitSpec:
    if "resource_type" not in raw:
        raise ModuleError(f"{ctx}: emit missing `resource_type`")
    rtype = raw["resource_type"]
    if rtype == "Encounter":
        return _parse_encounter_emit(raw, ctx)
    if rtype == "Observation":
        return _parse_observation_emit(raw, ctx)
    if rtype == "MedicationRequest":
        return _parse_medication_request_emit(raw, ctx)
    raise ModuleError(
        f"{ctx}: unsupported resource_type {rtype!r}; "
        f"choices: Encounter, Observation, MedicationRequest"
    )


def _parse_onset_age(raw: dict[str, Any], context: str) -> OnsetAgeRange:
    for required in ("min", "max"):
        if required not in raw:
            raise ModuleError(f"{context}: onset_age missing {required!r}")
    lo = int(raw["min"])
    hi = int(raw["max"])
    if lo < 0:
        raise ModuleError(f"{context}: onset_age.min {lo} must be >= 0")
    if hi < lo:
        raise ModuleError(f"{context}: onset_age.max {hi} < min {lo}")
    return OnsetAgeRange(min=lo, max=hi)


def _parse_condition(raw: dict[str, Any]) -> ConditionSpec:
    code = _parse_coding(raw["code"], f"condition {raw.get('id')!r}.code")
    prevalence, by_sex = _parse_prevalence(raw.get("prevalence", {}))
    emits_raw = raw.get("emits") or ()
    emits = tuple(
        _parse_emit(e, f"condition {raw.get('id')!r}.emits[{i}]")
        for i, e in enumerate(emits_raw)
    )
    # At most one Encounter per condition (the one all other resources link to).
    encounter_count = sum(1 for e in emits if isinstance(e, EncounterEmit))
    if encounter_count > 1:
        raise ModuleError(
            f"condition {raw.get('id')!r}: at most one Encounter emit per condition"
        )
    onset_age = (
        _parse_onset_age(raw["onset_age"], f"condition {raw.get('id')!r}.onset_age")
        if raw.get("onset_age")
        else None
    )
    return ConditionSpec(
        id=raw["id"],
        code=code,
        prevalence_by_bracket=prevalence,
        prevalence_by_sex=by_sex,
        emits=emits,
        onset_age=onset_age,
    )


def load_module_from_str(yaml_text: str) -> Module:
    """Parse a module YAML string into a validated Module."""
    try:
        data = yaml.safe_load(yaml_text)
    except yaml.YAMLError as exc:
        raise ModuleError(f"invalid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise ModuleError("module must be a mapping at the top level")

    for required in ("module", "version", "conditions"):
        if required not in data:
            raise ModuleError(f"missing required key: {required}")

    cites = tuple(Citation(**c) for c in data.get("cites") or [])
    conditions = tuple(_parse_condition(c) for c in data["conditions"])

    return Module(
        name=str(data["module"]),
        version=str(data["version"]),
        description=str(data.get("description", "")),
        cites=cites,
        conditions=conditions,
    )


def load_module(name: str) -> Module:
    """Load a bundled module by name from parker_atlas.modules.library."""
    pkg = resources.files("parker_atlas.modules.library")
    target = pkg.joinpath(f"{name}.yaml")
    if not target.is_file():
        bundled = ", ".join(list_bundled_modules()) or "(none)"
        raise ModuleError(f"no bundled module named {name!r}. Available: {bundled}")
    return load_module_from_str(target.read_text(encoding="utf-8"))


def list_bundled_modules() -> list[str]:
    """Return sorted names of all bundled modules."""
    pkg = resources.files("parker_atlas.modules.library")
    return sorted(
        f.name.removesuffix(".yaml")
        for f in pkg.iterdir()
        if f.name.endswith(".yaml")
    )


# -- Execution ---------------------------------------------------------------


def _find_bracket(age: int, brackets) -> tuple[int, int] | None:
    for lo, hi in brackets:
        if lo <= age <= hi:
            return (lo, hi)
    return None


def _lookup_prevalence(
    cond: ConditionSpec, age: int, sex: str
) -> float | None:
    if cond.prevalence_by_sex is not None:
        brackets = cond.prevalence_by_sex.get(sex)
        if brackets is None:
            return None
        key = _find_bracket(age, brackets.keys())
        return brackets.get(key) if key else None
    key = _find_bracket(age, cond.prevalence_by_bracket.keys())
    return cond.prevalence_by_bracket.get(key) if key else None


def _sample_value(rng: random.Random, rng_range: ValueRange) -> float:
    v = rng.uniform(rng_range.low, rng_range.high)
    if rng_range.precision == 0:
        return float(int(round(v)))
    return round(v, rng_range.precision)


def _resolve_when(when: str, today: date, onset_date: date | None) -> date:
    """Map a `when` keyword to the actual effective date for a sampled emit."""
    if when == "onset" and onset_date is not None:
        return onset_date
    return today


def _sample_observation(
    emit: ObservationEmit,
    rng: random.Random,
    *,
    effective_date: date,
) -> SampledObservation:
    if emit.components:
        components = tuple(
            SampledComponent(
                code=c.code,
                value=_sample_value(rng, c.value_range),
                unit=c.unit,
                unit_code=c.unit_code or c.unit,
            )
            for c in emit.components
        )
        return SampledObservation(
            spec_id=emit.spec_id,
            category=emit.category,
            code=emit.code,
            value=None,
            unit=None,
            unit_code=None,
            components=components,
            effective_date=effective_date,
            when=emit.when,
        )
    assert emit.value_range is not None and emit.unit is not None
    return SampledObservation(
        spec_id=emit.spec_id,
        category=emit.category,
        code=emit.code,
        value=_sample_value(rng, emit.value_range),
        unit=emit.unit,
        unit_code=emit.unit_code or emit.unit,
        components=(),
        effective_date=effective_date,
        when=emit.when,
    )


def _sample_emits(
    cond: ConditionSpec,
    rng: random.Random,
    *,
    today: date,
    onset_date: date | None,
) -> tuple[SampledResource, ...]:
    out: list[SampledResource] = []
    for emit in cond.emits:
        if rng.random() >= emit.probability:
            continue
        eff = _resolve_when(emit.when, today, onset_date)
        if isinstance(emit, EncounterEmit):
            out.append(
                SampledEncounter(
                    spec_id=emit.spec_id,
                    encounter_class=emit.encounter_class,
                    type_code=emit.type_code,
                    reason_code=emit.reason_code,
                    effective_date=eff,
                    when=emit.when,
                )
            )
        elif isinstance(emit, ObservationEmit):
            out.append(_sample_observation(emit, rng, effective_date=eff))
        elif isinstance(emit, MedicationRequestEmit):
            out.append(
                SampledMedicationRequest(
                    spec_id=emit.spec_id,
                    medication_code=emit.medication_code,
                    reason_code=emit.reason_code,
                    effective_date=eff,
                    when=emit.when,
                )
            )
        else:  # pragma: no cover — defensive
            raise AssertionError(f"unknown emit type {type(emit).__name__}")
    return tuple(out)


def _sample_onset_date(
    onset_age: OnsetAgeRange,
    current_age: int,
    today: date,
    rng: random.Random,
) -> date:
    """Sample a Condition.onsetDateTime for a patient currently `current_age` years old.

    If the patient is younger than `onset_age.min`, the condition is
    treated as just diagnosed (onset = today). Otherwise the onset age
    is sampled uniformly in [min, min(max, current_age)] and the date
    is computed by subtracting the implied years from `today`.
    """
    lo = onset_age.min
    hi = min(onset_age.max, current_age)
    if hi < lo:
        return today
    onset_age_years = rng.randint(lo, hi)
    years_ago = current_age - onset_age_years
    return today - timedelta(days=365 * years_ago)


def run_module(
    module: Module,
    age_years: int,
    sex: str,
    rng: random.Random,
    *,
    today: date | None = None,
) -> list[Diagnosis]:
    """Run a probability module for one patient; return sampled diagnoses."""
    today = today or date.today()
    out: list[Diagnosis] = []
    for cond in module.conditions:
        p = _lookup_prevalence(cond, age_years, sex)
        if p is None:
            continue
        if rng.random() < p:
            onset_date = (
                _sample_onset_date(cond.onset_age, age_years, today, rng)
                if cond.onset_age
                else None
            )
            sampled = _sample_emits(cond, rng, today=today, onset_date=onset_date)
            out.append(
                Diagnosis(
                    condition=cond,
                    sampled_resources=sampled,
                    onset_date=onset_date,
                )
            )
    return out

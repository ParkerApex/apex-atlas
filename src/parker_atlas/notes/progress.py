"""
Template-based progress notes.

The note generator takes structured patient + diagnosis data and emits a
plaintext markdown note. It is deterministic given its inputs (no RNG,
no calls out), which keeps generated notes reproducible across seeded
runs.

The renderer surfaces:
- The patient's full problem list (all fired conditions in `diagnoses`)
- The most recent observation per (system, code) — vitals + labs the
  modules emitted, sorted by effective_date so today's BP wins over
  the diagnosis-day BP
- All active MedicationRequest displays (deduplicated)

LLM-mode is a stub: the strategy enum and dispatch surface exist so
future authoring can swap in an LLM call without changing the call
sites that drive `atlas generate --with-notes`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum

from parker_atlas.modules.runtime import (
    Diagnosis,
    SampledMedicationRequest,
    SampledObservation,
)


class NoteStrategy(str, Enum):
    TEMPLATE = "template"
    LLM = "llm"  # Reserved for M4; raises NotImplementedError today.


@dataclass(frozen=True)
class NoteContext:
    """Structured inputs the templates draw from.

    `diagnoses` is the patient's full problem list (every fired condition).
    `primary_diagnosis`, when set, identifies the condition this note is
    centered on — used to pick the Subjective focus. When unset, the first
    entry in `diagnoses` is treated as primary.

    Vitals / labs / meds are pulled from the diagnoses' sampled_resources
    at render time; the renderer keeps the most recent value per
    (system, code) so today's BP supersedes the diagnosis-day BP.
    """

    patient_display_name: str
    age_years: int
    sex: str  # "female" | "male" — matches AdministrativeGender values
    today: date
    diagnoses: tuple[Diagnosis, ...] = field(default_factory=tuple)
    primary_diagnosis: Diagnosis | None = None


# LOINC code for blood-pressure panel (multi-component); the renderer
# special-cases this to format SBP/DBP on one line.
_LOINC_BP_PANEL = "85354-9"
_LOINC_SBP = "8480-6"
_LOINC_DBP = "8462-4"


def _format_diagnosis_line(dx: Diagnosis) -> str:
    code = dx.condition.code
    onset = (
        f" (onset {dx.onset_date.isoformat()})"
        if dx.onset_date is not None
        else ""
    )
    return f"- {code.display} ({code.system} {code.code}){onset}"


def _format_observation_line(obs: SampledObservation) -> str:
    """Format one observation as a single bullet line.

    Multi-component BP panels render as `SBP/DBP unit`. Other
    multi-component obs render as a comma-separated value list. Single-
    value observations render as `display: value unit (date)`.
    """
    date_label = obs.effective_date.isoformat()
    if obs.components:
        if obs.code.code == _LOINC_BP_PANEL:
            sbp = next(
                (c.value for c in obs.components if c.code.code == _LOINC_SBP),
                None,
            )
            dbp = next(
                (c.value for c in obs.components if c.code.code == _LOINC_DBP),
                None,
            )
            if sbp is not None and dbp is not None:
                return (
                    f"- Blood pressure: {sbp:.0f}/{dbp:.0f} mmHg ({date_label})"
                )
        # Generic multi-component: show each as "label value unit".
        parts = [
            f"{c.code.display} {c.value:g} {c.unit}" for c in obs.components
        ]
        return f"- {obs.code.display}: {', '.join(parts)} ({date_label})"
    assert obs.value is not None and obs.unit is not None
    # Strip insignificant trailing zeros via :g but keep clinically
    # familiar precision (e.g. 7.4, not 7.4000).
    return f"- {obs.code.display}: {obs.value:g} {obs.unit} ({date_label})"


def _collect_recent_observations(
    diagnoses: tuple[Diagnosis, ...],
) -> list[SampledObservation]:
    """Return the most-recent observation per (system, code).

    Ties on date are broken by the order of appearance so output is
    deterministic. Observations are returned sorted by effective_date
    descending (most recent first), then by display name for stability.
    """
    by_key: dict[tuple[str, str], SampledObservation] = {}
    for dx in diagnoses:
        for sr in dx.sampled_resources:
            if not isinstance(sr, SampledObservation):
                continue
            key = (sr.code.system, sr.code.code)
            existing = by_key.get(key)
            if existing is None or sr.effective_date > existing.effective_date:
                by_key[key] = sr
    return sorted(
        by_key.values(),
        key=lambda o: (-o.effective_date.toordinal(), o.code.display),
    )


def _collect_active_medications(
    diagnoses: tuple[Diagnosis, ...],
) -> list[str]:
    """Return deduplicated medication display strings, sorted alphabetically."""
    seen: set[tuple[str, str]] = set()
    displays: list[str] = []
    for dx in diagnoses:
        for sr in dx.sampled_resources:
            if not isinstance(sr, SampledMedicationRequest):
                continue
            key = (sr.medication_code.system, sr.medication_code.code)
            if key in seen:
                continue
            seen.add(key)
            displays.append(sr.medication_code.display)
    return sorted(displays)


def build_progress_note_text(ctx: NoteContext) -> str:
    """Render a markdown progress note from structured context.

    The body is grounded in the diagnoses' sampled vitals, labs, and
    medications. M4's LLM-assisted authoring will replace the prose
    sections (Subjective, Assessment & Plan) with model-generated
    narrative while keeping the structured Objective / Medications
    sections identical.
    """
    if not ctx.diagnoses:
        problem_list = "_No active problems on file._"
    else:
        problem_list = "\n".join(_format_diagnosis_line(dx) for dx in ctx.diagnoses)

    primary = ctx.primary_diagnosis or (ctx.diagnoses[0] if ctx.diagnoses else None)
    primary_display = (
        primary.condition.code.display if primary is not None else "general care"
    )

    observations = _collect_recent_observations(ctx.diagnoses)
    medications = _collect_active_medications(ctx.diagnoses)

    objective_lines: list[str]
    if observations:
        objective_lines = [_format_observation_line(o) for o in observations]
    else:
        objective_lines = ["_No vitals or labs on file for this encounter._"]

    medication_lines: list[str]
    if medications:
        medication_lines = [f"- {m}" for m in medications]
    else:
        medication_lines = ["_None on file._"]

    lines: list[str] = [
        "# Progress Note",
        "",
        f"**Patient:** {ctx.patient_display_name}",
        f"**Age / Sex:** {ctx.age_years} / {ctx.sex}",
        f"**Date:** {ctx.today.isoformat()}",
        "",
        "## Active Problems",
        problem_list,
        "",
        "## Subjective",
        f"Patient seen today for follow-up of {primary_display}.",
        "No new acute complaints documented in this synthetic record.",
        "",
        "## Objective",
        "",
        "### Vitals & labs (most recent)",
        *objective_lines,
        "",
        "### Active medications",
        *medication_lines,
        "",
        "## Assessment & Plan",
        f"Continue current management of {primary_display}. "
        "Reassess at next routine follow-up.",
        "",
        "---",
        "_Generated by APEX Atlas (template mode). "
        "This is synthetic data; no real patient is depicted._",
    ]
    return "\n".join(lines)


def render_note(ctx: NoteContext, strategy: NoteStrategy = NoteStrategy.TEMPLATE) -> str:
    """Dispatch to the chosen renderer. LLM mode is reserved for M4."""
    if strategy is NoteStrategy.TEMPLATE:
        return build_progress_note_text(ctx)
    if strategy is NoteStrategy.LLM:
        raise NotImplementedError(
            "NoteStrategy.LLM is reserved for Milestone 4. "
            "Use NoteStrategy.TEMPLATE for the current build."
        )
    raise ValueError(f"unknown NoteStrategy: {strategy!r}")

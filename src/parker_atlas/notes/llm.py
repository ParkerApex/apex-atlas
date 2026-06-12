"""
LLM-backed clinical note rendering (Milestone 4, first cut).

The LLM renderer takes the same `NoteContext` that drives the template
path, projects its structured data into a strict JSON payload, and asks
the configured LLM provider to author the *narrative* sections (Subjective; Assessment &
Plan) only. The Objective / Medications / Active Problems sections come
straight from the structured data — those are not negotiable and not
re-stated by the model — so we never let the LLM fabricate vitals,
labs, codes, or medications that aren't in the source bundle.

Determinism: temperature is 0 by default, and the system prompt is
prompt-cached so that across a cohort run we pay full input tokens once
and a 10% cache-read cost on every subsequent patient. Output text is
*not* guaranteed bit-stable across model versions, so the renderer
records the model id alongside the note.

Failure mode: if the `anthropic` SDK isn't installed or no API key is
present, the LLM strategy raises a clear error. Callers that want a
graceful fallback can catch `LLMNotesUnavailable` and re-dispatch to
`NoteStrategy.TEMPLATE`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from parker_atlas.modules.runtime import SampledObservation
from parker_atlas.notes.progress import (
    NoteContext,
    _collect_active_medications,
    _collect_recent_observations,
    _format_diagnosis_line,
    _format_observation_line,
)


DEFAULT_LLM_MODEL = "claude-haiku-4-5-20251001"
"""Default fast model for one-off narrative (Anthropic Haiku tier).

A 100-patient cohort with the default model + prompt caching costs roughly a few
cents at current pricing. Override with --llm-model for higher narrative
quality when authoring reference cohorts or demos.
"""


class LLMNotesUnavailable(RuntimeError):
    """Raised when the LLM strategy is requested but cannot be served."""


@dataclass(frozen=True, slots=True)
class LLMNoteResult:
    """Full provenance for an LLM-authored note.

    `text` is the rendered markdown. `model` records which LLM model
    produced the narrative. `cache_read_input_tokens` lets cohort runs
    surface cache hit rate in the summary.
    """

    text: str
    model: str
    input_tokens: int
    output_tokens: int
    cache_read_input_tokens: int
    cache_creation_input_tokens: int


_SYSTEM_PROMPT = """\
You are a clinical documentation assistant authoring narrative sections of
a progress note for a SYNTHETIC patient. No real patient is depicted.

Your job:
1. Write the Subjective section (one short paragraph, plain narrative)
   describing the visit from the patient's perspective, grounded entirely
   in the structured data provided. Do NOT invent vitals, labs, doses,
   medication names, or diagnoses that are not in the structured data.
2. Write the Assessment & Plan section as a brief, numbered list, one
   line per active problem from the problem list. Each line states the
   clinical impression and a concrete next step (lifestyle, medication
   continuation, follow-up interval, or referral). Stay consistent with
   any medications already on the medication list — do not change doses
   or substitute drugs.

Rules:
- Never reference dates, providers, encounter ids, or values that are
  not present in the supplied structured data.
- Never write "I" or speak as the clinician in first person.
- Output strict JSON matching this schema, and nothing else:
  {"subjective": "<paragraph>", "assessment_and_plan": "<markdown numbered list>"}
- Keep prose tight. Subjective <= 80 words. Assessment & Plan <= 150 words.
- This is synthetic data; do not add disclaimers — the renderer adds one.
"""


def _structured_payload(ctx: NoteContext) -> dict[str, Any]:
    """Project NoteContext into the strict JSON we pass to the model.

    The model only sees this payload — no FHIR resources, no raw bundles.
    That keeps the prompt tight and the surface area small.
    """
    observations = _collect_recent_observations(ctx.diagnoses)
    medications = _collect_active_medications(ctx.diagnoses)

    def _obs_to_json(obs: SampledObservation) -> dict[str, Any]:
        out: dict[str, Any] = {
            "code": obs.code.code,
            "display": obs.code.display,
            "system": obs.code.system,
            "date": obs.effective_date.isoformat(),
        }
        if obs.components:
            out["components"] = [
                {
                    "code": c.code.code,
                    "display": c.code.display,
                    "value": c.value,
                    "unit": c.unit,
                }
                for c in obs.components
            ]
        else:
            out["value"] = obs.value
            out["unit"] = obs.unit
        return out

    diagnoses_json = [
        {
            "id": dx.condition.id,
            "code": dx.condition.code.code,
            "display": dx.condition.code.display,
            "system": dx.condition.code.system,
            "onset_date": (
                dx.onset_date.isoformat() if dx.onset_date is not None else None
            ),
        }
        for dx in ctx.diagnoses
    ]

    primary = ctx.primary_diagnosis or (ctx.diagnoses[0] if ctx.diagnoses else None)
    primary_id = primary.condition.id if primary is not None else None

    return {
        "patient": {
            "age_years": ctx.age_years,
            "sex": ctx.sex,
        },
        "visit_date": ctx.today.isoformat(),
        "diagnoses": diagnoses_json,
        "primary_diagnosis_id": primary_id,
        "observations_most_recent": [_obs_to_json(o) for o in observations],
        "active_medications": medications,
    }


def _author_narrative(
    payload: dict[str, Any],
    *,
    model: str,
    api_key: str | None,
    max_tokens: int,
    temperature: float,
    provider: str | None = None,
) -> tuple[dict[str, str], dict[str, int], str]:
    """Call the configured LLM provider. Returns (parsed_json, usage_dict, model_id)."""
    from parker_atlas.notes.providers import resolve_provider

    resolved = resolve_provider(provider)
    return resolved.complete_json(
        system_prompt=_SYSTEM_PROMPT,
        user_payload=payload,
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
    )


def _assemble_note_markdown(
    ctx: NoteContext, narrative: dict[str, str], *, model: str
) -> str:
    """Stitch model narrative into the structured note skeleton.

    Active Problems / Objective / Medications come straight from the
    structured data — only Subjective and Assessment & Plan are LLM-
    authored. This keeps the bill of materials for every note auditable
    against the source bundle.
    """
    if not ctx.diagnoses:
        problem_list = "_No active problems on file._"
    else:
        problem_list = "\n".join(_format_diagnosis_line(dx) for dx in ctx.diagnoses)

    observations = _collect_recent_observations(ctx.diagnoses)
    medications = _collect_active_medications(ctx.diagnoses)

    objective_lines = (
        [_format_observation_line(o) for o in observations]
        if observations
        else ["_No vitals or labs on file for this encounter._"]
    )
    medication_lines = (
        [f"- {m}" for m in medications]
        if medications
        else ["_None on file._"]
    )

    subjective = (narrative.get("subjective") or "").strip()
    assessment = (narrative.get("assessment_and_plan") or "").strip()

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
        subjective,
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
        assessment,
        "",
        "---",
        f"_Generated by APEX Atlas (LLM mode, {model}). "
        "Narrative sections are model-authored from structured data. "
        "This is synthetic data; no real patient is depicted._",
    ]
    return "\n".join(lines)


def render_llm_note(
    ctx: NoteContext,
    *,
    model: str | None = None,
    api_key: str | None = None,
    max_tokens: int = 800,
    temperature: float = 0.0,
    provider: str | None = None,
) -> LLMNoteResult:
    """Render a progress note with LLM-authored narrative sections.

    Raises `LLMNotesUnavailable` if the SDK is missing or the API call
    cannot be completed cleanly. Callers should catch this and decide
    whether to fall back to the template renderer or fail the run.

    Provider selection: `provider=` argument, else `ATLAS_LLM_PROVIDER`
    env var (`anthropic` default, `openai` optional).
    """
    from parker_atlas.notes.providers import DEFAULT_OPENAI_MODEL, resolve_provider

    chosen = (provider or os.environ.get("ATLAS_LLM_PROVIDER", "anthropic")).strip().lower()
    if model is None:
        model = DEFAULT_LLM_MODEL if chosen == "anthropic" else DEFAULT_OPENAI_MODEL

    if chosen == "anthropic":
        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise LLMNotesUnavailable(
                "LLM note authoring requires ANTHROPIC_API_KEY in the environment "
                "(or pass api_key= explicitly)."
            )
    elif chosen == "openai":
        key = api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise LLMNotesUnavailable(
                "OpenAI note authoring requires OPENAI_API_KEY in the environment "
                "(or pass api_key= explicitly)."
            )
    else:
        resolve_provider(chosen)  # raises with clear message
        key = api_key

    payload = _structured_payload(ctx)
    narrative, usage, model_id = _author_narrative(
        payload,
        model=model,
        api_key=key,
        max_tokens=max_tokens,
        temperature=temperature,
        provider=chosen,
    )
    text = _assemble_note_markdown(ctx, narrative, model=model_id)
    return LLMNoteResult(
        text=text,
        model=model_id,
        input_tokens=usage["input_tokens"],
        output_tokens=usage["output_tokens"],
        cache_read_input_tokens=usage["cache_read_input_tokens"],
        cache_creation_input_tokens=usage["cache_creation_input_tokens"],
    )

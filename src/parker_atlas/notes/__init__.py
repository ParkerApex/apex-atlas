"""
Clinical note generation for synthetic patients.

Two strategies are exposed via NoteStrategy:

- TEMPLATE — deterministic, structured-data-grounded fill-ins. Always
  available, no API keys, no external calls. The first-cut shape used
  by every Atlas note today.
- LLM — provider-authored narrative sections (Subjective, Assessment &
  Plan) grounded in structured data. Available when ANTHROPIC_API_KEY
  is set and the `[llm]` extra is installed; raises LLMNotesUnavailable
  otherwise so callers can decide whether to fall back to TEMPLATE.
"""

from parker_atlas.notes.progress import (
    NoteContext,
    NoteStrategy,
    build_progress_note_text,
    render_note,
)

__all__ = [
    "DEFAULT_LLM_MODEL",
    "LLMNoteResult",
    "LLMNotesUnavailable",
    "NoteContext",
    "NoteStrategy",
    "build_discharge_summary_text",
    "build_progress_note_text",
    "build_radiology_report_text",
    "render_llm_note",
    "render_note",
]


def __getattr__(name: str):
    if name == "build_discharge_summary_text":
        from parker_atlas.notes.discharge import build_discharge_summary_text

        return build_discharge_summary_text
    if name == "build_radiology_report_text":
        from parker_atlas.notes.radiology import build_radiology_report_text

        return build_radiology_report_text
    # Lazy import so `from parker_atlas.notes import NoteStrategy` doesn't
    # require the anthropic SDK to be installed.
    if name in {
        "LLMNotesUnavailable",
        "LLMNoteResult",
        "render_llm_note",
        "DEFAULT_LLM_MODEL",
    }:
        from parker_atlas.notes import llm

        return getattr(llm, name)
    raise AttributeError(name)

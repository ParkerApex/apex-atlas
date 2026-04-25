"""
Clinical note generation for synthetic patients.

Two strategies are exposed via NoteStrategy:

- TEMPLATE — deterministic, structured-data-grounded fill-ins. Always
  available, no API keys, no external calls. The first-cut shape used
  by every Atlas note today.
- LLM — placeholder for M4 LLM-assisted authoring. Importing it now
  raises NotImplementedError; the API surface is here so callers can
  pin against the eventual contract without churn later.
"""

from parker_atlas.notes.progress import (
    NoteContext,
    NoteStrategy,
    build_progress_note_text,
    render_note,
)

__all__ = [
    "NoteContext",
    "NoteStrategy",
    "build_progress_note_text",
    "render_note",
]

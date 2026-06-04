"""
Research-grounded module authoring.

The `author` package turns a cited **research dossier** into a *draft*
clinical module plus a matching *draft* fidelity expectation, then validates
both by round-tripping them through the real runtime loaders
(`load_module_from_str`, `load_expectation_from_str`) before anything is
written. This mirrors the `atlas ingest` pattern: malformed output fails at
author time, not at `atlas validate --cohort` time.

The dossier is the human-reviewable artifact. Synthesis is deterministic (no
LLM in the loop) so the generated module/expectation are mechanically derived
from cited numbers and are fully testable. Drafts land in a staging directory
*outside* the bundled library, so the runtime never loads unreviewed work
until `atlas author promote` installs it.

Phase 2 adds `research.py` — an in-package, web_search-backed command that
produces a dossier autonomously against the same contract.
"""

from __future__ import annotations

from parker_atlas.author.dossier import Dossier, DossierError, load_dossier_from_str
from parker_atlas.author.promote import promote_draft
from parker_atlas.author.research import (
    AuthorResearchUnavailable,
    research_condition,
)
from parker_atlas.author.synthesize import (
    AuthorError,
    synthesize_expectation,
    synthesize_module,
)

__all__ = [
    "AuthorError",
    "AuthorResearchUnavailable",
    "Dossier",
    "DossierError",
    "load_dossier_from_str",
    "promote_draft",
    "research_condition",
    "synthesize_expectation",
    "synthesize_module",
]

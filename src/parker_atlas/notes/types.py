"""Note type identifiers and parsing for multi-type clinical documentation."""

from __future__ import annotations

from enum import StrEnum

from parker_atlas.modules.runtime import SampledProcedure


class NoteType(StrEnum):
    PROGRESS = "progress"
    DISCHARGE = "discharge"
    RADIOLOGY = "radiology"


_DEFAULT_NOTE_TYPES = frozenset({NoteType.PROGRESS})

_IMAGING_TOKENS = (
    "mri",
    "magnetic resonance",
    "ct ",
    "computed tomography",
    "tomography",
    "x-ray",
    "x ray",
    "radiograph",
    "mammograph",
    "ultrasound",
    "ultrasonograph",
    "echocardiograph",
    "imaging",
    "radiologic",
)


def parse_note_types(raw: str | None) -> frozenset[NoteType]:
    """Parse a comma-separated `--note-types` value."""
    if not raw or not raw.strip():
        return _DEFAULT_NOTE_TYPES
    out: set[NoteType] = set()
    for part in raw.split(","):
        token = part.strip().lower()
        if not token:
            continue
        try:
            out.add(NoteType(token))
        except ValueError as exc:
            allowed = ", ".join(t.value for t in NoteType)
            raise ValueError(
                f"unknown note type {token!r}; expected one of: {allowed}"
            ) from exc
    return frozenset(out) if out else _DEFAULT_NOTE_TYPES


def is_imaging_procedure(proc: SampledProcedure) -> bool:
    """Heuristic: SNOMED/ display text suggests diagnostic imaging."""
    hay = proc.code.display.lower()
    return any(tok in hay for tok in _IMAGING_TOKENS)


def is_inpatient_encounter_class(class_code: str) -> bool:
    """IMP and EMER visits warrant discharge summaries in Atlas templates."""
    return class_code in {"IMP", "EMER"}

"""
FHIR R4 DocumentReference resource construction for clinical notes.

This is the minimal first cut: a base FHIR DocumentReference (not US Core
DocumentReference 6.1 yet — that profile requires identifier, author,
date, and category slicing, which the note pipeline doesn't have a
realistic source for until M4). Schema-valid against the R4 spec; the
US Core profile claim is intentionally omitted so future tightening
doesn't silently downgrade synthetic notes.

The builder takes a prebuilt note body (markdown) and wraps it as a
content[].attachment with base64 data + contentType. Note generation
itself (templates today, LLM in M4) lives in `parker_atlas.notes`.
"""

from __future__ import annotations

import base64
import uuid
from datetime import date, datetime, time, timezone
from typing import Any

from fhir.resources.R4B.documentreference import (
    DocumentReference as _DocumentReference,
)

from parker_atlas.gpx import GPX


def _fhir_instant(value: date | datetime) -> str:
    """Format `value` as a FHIR R4 `instant` (timestamp with timezone).

    DocumentReference.date is typed `instant`, which requires a time
    component AND a timezone. Bare `date` values are pinned to noon UTC
    so synthetic notes have a deterministic, timezone-correct timestamp.
    """
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    dt = datetime.combine(value, time(12, 0, 0), tzinfo=timezone.utc)
    return dt.isoformat()

_URL_NAMESPACE = uuid.UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8")

# LOINC document type codes used by Parker Atlas note types.
LOINC_PROGRESS_NOTE = "11506-3"
LOINC_HISTORY_AND_PHYSICAL = "34117-2"
LOINC_DISCHARGE_SUMMARY = "18842-5"

LOINC_SYSTEM = "http://loinc.org"


def document_reference_id(gpx: GPX, doc_spec_id: str) -> str:
    """Deterministic DocumentReference.id from GPX + spec id (one note ↔ one id)."""
    return str(uuid.uuid5(_URL_NAMESPACE, f"{gpx}:doc:{doc_spec_id}"))


def build_document_reference_resource(
    gpx: GPX,
    patient_fullurl: str,
    *,
    doc_spec_id: str,
    note_text: str,
    note_type_code: str = LOINC_PROGRESS_NOTE,
    note_type_display: str = "Progress note",
    content_type: str = "text/markdown",
    authored_on: date | datetime,
    encounter_fullurl: str | None = None,
) -> dict[str, Any]:
    """Build a DocumentReference wrapping a clinical note as inline content.

    `note_text` is encoded as base64 and embedded in
    content[0].attachment.data. The textual contentType (default
    text/markdown) round-trips cleanly through downstream pipelines
    that decode base64 + match on contentType.

    `encounter_fullurl`, when provided, populates context.encounter so
    the note is linked back to the visit that produced it.
    """
    encoded = base64.b64encode(note_text.encode("utf-8")).decode("ascii")
    resource: dict[str, Any] = {
        "resourceType": "DocumentReference",
        "id": document_reference_id(gpx, doc_spec_id),
        "meta": {
            "tag": [GPX.synthetic_meta_tag()],
        },
        "status": "current",
        "type": {
            "coding": [
                {
                    "system": LOINC_SYSTEM,
                    "code": note_type_code,
                    "display": note_type_display,
                }
            ],
            "text": note_type_display,
        },
        "category": [
            {
                "coding": [
                    {
                        "system": LOINC_SYSTEM,
                        "code": "47039-3",
                        "display": "Hospital Admission history and physical note",
                    }
                ]
            }
        ],
        "subject": {"reference": patient_fullurl},
        "date": _fhir_instant(authored_on),
        "content": [
            {
                "attachment": {
                    "contentType": content_type,
                    "data": encoded,
                }
            }
        ],
    }
    if encounter_fullurl is not None:
        resource["context"] = {"encounter": [{"reference": encounter_fullurl}]}
    _DocumentReference.model_validate(resource)
    return resource

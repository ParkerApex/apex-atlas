"""Emit DocumentReference resources for configured note types."""

from __future__ import annotations

from datetime import date
from typing import Any

from parker_atlas.fhir.document_reference import (
    LOINC_DISCHARGE_SUMMARY,
    LOINC_PROGRESS_NOTE,
    build_document_reference_resource,
)
from parker_atlas.fhir.procedure import procedure_id
from parker_atlas.gpx import GPX
from parker_atlas.modules.runtime import Diagnosis, SampledProcedure
from parker_atlas.notes.discharge import build_discharge_summary_text
from parker_atlas.notes.progress import NoteContext, NoteStrategy, build_progress_note_text
from parker_atlas.notes.radiology import build_radiology_report_text
from parker_atlas.notes.types import NoteType, is_imaging_procedure, is_inpatient_encounter_class

LOINC_RADIOLOGY_REPORT = "18748-4"
LOINC_RADIOLOGY_DISPLAY = "Diagnostic imaging study report"


def build_note_document_references(
    *,
    gpx: GPX,
    patient_url: str,
    mod_name: str,
    patient_display_name: str,
    age_years: int,
    sex: str,
    today: date,
    all_diagnoses: tuple[Diagnosis, ...],
    dx: Diagnosis,
    dx_emits: list[dict[str, Any]],
    note_types: frozenset[NoteType],
    notes_strategy: NoteStrategy,
    llm_model: str | None,
) -> list[dict[str, Any]]:
    """Build DocumentReference dicts for the requested note types."""
    docs: list[dict[str, Any]] = []
    ctx = NoteContext(
        patient_display_name=patient_display_name,
        age_years=age_years,
        sex=sex,
        today=today,
        diagnoses=all_diagnoses,
        primary_diagnosis=dx,
    )

    default_encounter_url: str | None = None
    for resource in dx_emits:
        if resource.get("resourceType") == "Encounter":
            from parker_atlas.fhir.bundle import fullurl_for_resource

            default_encounter_url = fullurl_for_resource(gpx, resource)
            break

    if NoteType.PROGRESS in note_types:
        if notes_strategy is NoteStrategy.LLM:
            from parker_atlas.notes import render_llm_note

            llm_kwargs = {"model": llm_model} if llm_model else {}
            note_text = render_llm_note(ctx, **llm_kwargs).text
        else:
            note_text = build_progress_note_text(ctx)
        docs.append(
            build_document_reference_resource(
                gpx=gpx,
                patient_fullurl=patient_url,
                doc_spec_id=f"progress_{mod_name}_{dx.condition.id}",
                note_text=note_text,
                note_type_code=LOINC_PROGRESS_NOTE,
                note_type_display="Progress note",
                authored_on=today,
                encounter_fullurl=default_encounter_url,
            )
        )

    if NoteType.DISCHARGE in note_types:
        for resource in dx_emits:
            if resource.get("resourceType") != "Encounter":
                continue
            class_code = resource.get("class", {}).get("code", "")
            if not is_inpatient_encounter_class(class_code):
                continue
            from parker_atlas.fhir.bundle import fullurl_for_resource

            enc_url = fullurl_for_resource(gpx, resource)
            period = resource.get("period") or {}
            admission_date = period.get("start")
            note_text = build_discharge_summary_text(
                ctx,
                encounter_class=class_code,
                admission_date=admission_date,
            )
            enc_id = resource.get("id", "enc")
            docs.append(
                build_document_reference_resource(
                    gpx=gpx,
                    patient_fullurl=patient_url,
                    doc_spec_id=f"discharge_{mod_name}_{dx.condition.id}_{enc_id}",
                    note_text=note_text,
                    note_type_code=LOINC_DISCHARGE_SUMMARY,
                    note_type_display="Discharge summary",
                    authored_on=today,
                    encounter_fullurl=enc_url,
                )
            )

    if NoteType.RADIOLOGY in note_types:
        for sr in dx.sampled_resources:
            if not isinstance(sr, SampledProcedure) or not is_imaging_procedure(sr):
                continue
            note_text = build_radiology_report_text(ctx, sr)
            proc_enc_url = default_encounter_url
            expected_proc_id = procedure_id(gpx, sr.spec_id)
            for resource in dx_emits:
                if resource.get("resourceType") != "Procedure":
                    continue
                if resource.get("id") == expected_proc_id:
                    from parker_atlas.fhir.bundle import fullurl_for_resource

                    enc_ref = resource.get("encounter")
                    if isinstance(enc_ref, dict) and enc_ref.get("reference"):
                        proc_enc_url = enc_ref["reference"]
                    else:
                        proc_enc_url = fullurl_for_resource(gpx, resource)
                    break
            docs.append(
                build_document_reference_resource(
                    gpx=gpx,
                    patient_fullurl=patient_url,
                    doc_spec_id=f"radiology_{mod_name}_{sr.spec_id}",
                    note_text=note_text,
                    note_type_code=LOINC_RADIOLOGY_REPORT,
                    note_type_display=LOINC_RADIOLOGY_DISPLAY,
                    authored_on=sr.effective_date,
                    encounter_fullurl=proc_enc_url,
                )
            )

    return docs

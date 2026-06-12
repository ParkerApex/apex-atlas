#!/usr/bin/env python3
"""Tests for discharge and radiology note templates."""

from __future__ import annotations

from datetime import date

from parker_atlas.modules.runtime import Coding, ConditionSpec, Diagnosis, SampledProcedure
from parker_atlas.notes.discharge import build_discharge_summary_text
from parker_atlas.notes.progress import NoteContext
from parker_atlas.notes.radiology import build_radiology_report_text
from parker_atlas.notes.types import is_imaging_procedure


def _dx(display: str) -> Diagnosis:
    return Diagnosis(
        condition=ConditionSpec(
            id="cond1",
            code=Coding(system="http://snomed.info/sct", code="1", display=display),
            prevalence_by_bracket={(0, 99): 1.0},
        ),
        sampled_resources=(),
        onset_date=date(2024, 1, 1),
    )


def test_discharge_summary_includes_setting_and_primary_dx() -> None:
    ctx = NoteContext(
        patient_display_name="Doe, Jane",
        age_years=67,
        sex="female",
        today=date(2026, 6, 1),
        diagnoses=(_dx("Pneumonia"),),
        primary_diagnosis=_dx("Pneumonia"),
    )
    text = build_discharge_summary_text(ctx, encounter_class="IMP", admission_date="2026-05-28")
    assert "# Discharge Summary" in text
    assert "Pneumonia" in text
    assert "Inpatient (IMP)" in text
    assert "2026-05-28" in text


def test_radiology_report_links_procedure() -> None:
    proc = SampledProcedure(
        spec_id="mri_brain",
        code=Coding(
            system="http://snomed.info/sct",
            code="241615005",
            display="Magnetic resonance imaging of brain (procedure)",
        ),
        reason_code=None,
        effective_date=date(2026, 3, 10),
        when="today",
        link_to=None,
    )
    assert is_imaging_procedure(proc)
    ctx = NoteContext(
        patient_display_name="Smith, John",
        age_years=72,
        sex="male",
        today=date(2026, 3, 11),
        diagnoses=(_dx("Stroke"),),
        primary_diagnosis=_dx("Stroke"),
    )
    text = build_radiology_report_text(ctx, proc)
    assert "# Radiology Report" in text
    assert "Magnetic resonance imaging of brain" in text
    assert "Stroke" in text

"""Tests for the template-based progress-note generator."""

from __future__ import annotations

from datetime import date

import pytest

from parker_atlas.modules.runtime import Coding, ConditionSpec, Diagnosis
from parker_atlas.notes import (
    NoteContext,
    NoteStrategy,
    build_progress_note_text,
    render_note,
)


def _make_dx(spec_id: str, display: str, *, onset: date | None = None) -> Diagnosis:
    return Diagnosis(
        condition=ConditionSpec(
            id=spec_id,
            code=Coding(system="http://snomed.info/sct", code="1", display=display),
            prevalence_by_bracket={(0, 99): 1.0},
        ),
        sampled_resources=(),
        onset_date=onset,
    )


class TestProgressNoteTemplate:
    def test_includes_patient_demographics(self):
        ctx = NoteContext(
            patient_display_name="Doe, Jane",
            age_years=58,
            sex="female",
            today=date(2026, 4, 23),
            diagnoses=(_make_dx("htn", "Essential hypertension"),),
        )
        text = build_progress_note_text(ctx)
        assert "Doe, Jane" in text
        assert "58" in text
        assert "female" in text
        assert "2026-04-23" in text

    def test_lists_diagnoses_with_codes(self):
        ctx = NoteContext(
            patient_display_name="Smith, John",
            age_years=70,
            sex="male",
            today=date(2026, 4, 23),
            diagnoses=(
                _make_dx("htn", "Essential hypertension"),
                _make_dx("dm2", "Type 2 diabetes mellitus"),
            ),
        )
        text = build_progress_note_text(ctx)
        assert "Essential hypertension" in text
        assert "Type 2 diabetes mellitus" in text
        assert "http://snomed.info/sct" in text

    def test_includes_onset_date_when_present(self):
        ctx = NoteContext(
            patient_display_name="Smith, John",
            age_years=70,
            sex="male",
            today=date(2026, 4, 23),
            diagnoses=(_make_dx("htn", "HTN", onset=date(2018, 6, 1)),),
        )
        text = build_progress_note_text(ctx)
        assert "2018-06-01" in text

    def test_handles_no_diagnoses(self):
        ctx = NoteContext(
            patient_display_name="Smith, John",
            age_years=30,
            sex="male",
            today=date(2026, 4, 23),
        )
        text = build_progress_note_text(ctx)
        assert "No active problems" in text
        assert "general care" in text

    def test_marks_synthetic_data(self):
        ctx = NoteContext(
            patient_display_name="X",
            age_years=40,
            sex="male",
            today=date(2026, 4, 23),
        )
        text = build_progress_note_text(ctx)
        assert "synthetic" in text.lower()


class TestNoteRendererDispatch:
    def test_template_strategy_calls_template(self):
        ctx = NoteContext(
            patient_display_name="X",
            age_years=40,
            sex="male",
            today=date(2026, 4, 23),
        )
        # Default strategy is template; explicit and implicit should match.
        assert render_note(ctx) == build_progress_note_text(ctx)
        assert render_note(ctx, NoteStrategy.TEMPLATE) == build_progress_note_text(ctx)

    def test_llm_strategy_raises_not_implemented(self):
        ctx = NoteContext(
            patient_display_name="X",
            age_years=40,
            sex="male",
            today=date(2026, 4, 23),
        )
        with pytest.raises(NotImplementedError, match="Milestone 4"):
            render_note(ctx, NoteStrategy.LLM)

    def test_template_is_deterministic(self):
        # Same context → byte-identical output (no RNG, no clock reads).
        ctx = NoteContext(
            patient_display_name="Doe, Jane",
            age_years=58,
            sex="female",
            today=date(2026, 4, 23),
            diagnoses=(_make_dx("htn", "Essential hypertension"),),
        )
        assert build_progress_note_text(ctx) == build_progress_note_text(ctx)

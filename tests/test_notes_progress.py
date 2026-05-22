"""Tests for the template-based progress-note generator."""

from __future__ import annotations

from datetime import date

import pytest

from parker_atlas.modules.runtime import (
    Coding,
    ConditionSpec,
    Diagnosis,
    SampledComponent,
    SampledMedicationRequest,
    SampledObservation,
    SampledResource,
)
from parker_atlas.notes import (
    NoteContext,
    NoteStrategy,
    build_progress_note_text,
    render_note,
)


def _make_dx(
    spec_id: str,
    display: str,
    *,
    onset: date | None = None,
    sampled: tuple[SampledResource, ...] = (),
) -> Diagnosis:
    return Diagnosis(
        condition=ConditionSpec(
            id=spec_id,
            code=Coding(system="http://snomed.info/sct", code="1", display=display),
            prevalence_by_bracket={(0, 99): 1.0},
        ),
        sampled_resources=sampled,
        onset_date=onset,
    )


def _make_obs(
    *,
    code: str,
    display: str,
    value: float | None = None,
    unit: str | None = None,
    components: tuple[SampledComponent, ...] = (),
    effective: date,
) -> SampledObservation:
    return SampledObservation(
        spec_id=f"obs_{code}",
        category="vital-signs",
        code=Coding(system="http://loinc.org", code=code, display=display),
        value=value,
        unit=unit,
        unit_code=unit,
        components=components,
        effective_date=effective,
        when="today",
        link_to=None,
    )


def _make_med(*, code: str, display: str, effective: date) -> SampledMedicationRequest:
    return SampledMedicationRequest(
        spec_id=f"med_{code}",
        medication_code=Coding(
            system="http://www.nlm.nih.gov/research/umls/rxnorm",
            code=code,
            display=display,
        ),
        reason_code=None,
        effective_date=effective,
        when="today",
        link_to=None,
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

    def test_llm_strategy_unavailable_without_api_key(self, monkeypatch):
        # M4 wires NoteStrategy.LLM to the Claude renderer. Without an API
        # key the renderer raises LLMNotesUnavailable so callers can fall
        # back to TEMPLATE rather than crashing the run.
        from parker_atlas.notes import LLMNotesUnavailable

        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        ctx = NoteContext(
            patient_display_name="X",
            age_years=40,
            sex="male",
            today=date(2026, 4, 23),
        )
        with pytest.raises(LLMNotesUnavailable):
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


class TestNoteGroundingInStructuredData:
    def test_blood_pressure_panel_renders_systolic_over_diastolic(self):
        bp = _make_obs(
            code="85354-9",
            display="Blood pressure panel with all children optional",
            components=(
                SampledComponent(
                    code=Coding(
                        system="http://loinc.org", code="8480-6", display="SBP"
                    ),
                    value=132,
                    unit="mm[Hg]",
                    unit_code="mm[Hg]",
                ),
                SampledComponent(
                    code=Coding(
                        system="http://loinc.org", code="8462-4", display="DBP"
                    ),
                    value=84,
                    unit="mm[Hg]",
                    unit_code="mm[Hg]",
                ),
            ),
            effective=date(2026, 4, 20),
        )
        ctx = NoteContext(
            patient_display_name="X",
            age_years=60,
            sex="male",
            today=date(2026, 4, 23),
            diagnoses=(_make_dx("htn", "HTN", sampled=(bp,)),),
        )
        text = build_progress_note_text(ctx)
        assert "Blood pressure: 132/84 mmHg" in text
        assert "(2026-04-20)" in text

    def test_single_value_observation_renders_value_unit_date(self):
        a1c = _make_obs(
            code="4548-4",
            display="Hemoglobin A1c/Hemoglobin.total in Blood",
            value=7.4,
            unit="%",
            effective=date(2026, 3, 15),
        )
        ctx = NoteContext(
            patient_display_name="X",
            age_years=55,
            sex="female",
            today=date(2026, 4, 23),
            diagnoses=(_make_dx("dm", "DM", sampled=(a1c,)),),
        )
        text = build_progress_note_text(ctx)
        assert "Hemoglobin A1c" in text
        assert "7.4 %" in text
        assert "(2026-03-15)" in text

    def test_most_recent_observation_per_code_wins(self):
        # Two A1C observations, same LOINC. Renderer should keep only the
        # most recent one in the Objective section.
        a1c_old = _make_obs(
            code="4548-4",
            display="HbA1c",
            value=10.5,
            unit="%",
            effective=date(2025, 1, 10),
        )
        a1c_new = _make_obs(
            code="4548-4",
            display="HbA1c",
            value=7.4,
            unit="%",
            effective=date(2026, 3, 15),
        )
        ctx = NoteContext(
            patient_display_name="X",
            age_years=55,
            sex="female",
            today=date(2026, 4, 23),
            diagnoses=(_make_dx("dm", "DM", sampled=(a1c_old, a1c_new)),),
        )
        text = build_progress_note_text(ctx)
        assert "7.4 %" in text
        assert "10.5 %" not in text

    def test_active_medications_listed_and_deduplicated(self):
        lisinopril = _make_med(
            code="197361",
            display="Lisinopril 10 MG Oral Tablet",
            effective=date(2018, 6, 1),
        )
        metformin = _make_med(
            code="860975",
            display="Metformin 500 MG Oral Tablet",
            effective=date(2019, 4, 10),
        )
        # Same Lisinopril prescription appears under HTN dx and again under
        # CKD dx — should be listed once.
        ctx = NoteContext(
            patient_display_name="X",
            age_years=70,
            sex="male",
            today=date(2026, 4, 23),
            diagnoses=(
                _make_dx("htn", "HTN", sampled=(lisinopril,)),
                _make_dx("ckd", "CKD", sampled=(lisinopril,)),
                _make_dx("dm", "DM", sampled=(metformin,)),
            ),
        )
        text = build_progress_note_text(ctx)
        assert text.count("Lisinopril 10 MG Oral Tablet") == 1
        assert "Metformin 500 MG Oral Tablet" in text

    def test_no_observations_falls_back_to_placeholder(self):
        ctx = NoteContext(
            patient_display_name="X",
            age_years=40,
            sex="male",
            today=date(2026, 4, 23),
            diagnoses=(_make_dx("htn", "HTN"),),  # no sampled resources
        )
        text = build_progress_note_text(ctx)
        assert "No vitals or labs on file" in text
        assert "_None on file._" in text

    def test_primary_diagnosis_drives_subjective_and_plan(self):
        # When primary_diagnosis is set, the Subjective/Plan should reference
        # IT specifically, not just the first diagnosis in the tuple.
        ctx = NoteContext(
            patient_display_name="X",
            age_years=70,
            sex="male",
            today=date(2026, 4, 23),
            diagnoses=(
                _make_dx("htn", "Essential hypertension"),
                _make_dx("dm", "Diabetes mellitus"),
            ),
            primary_diagnosis=_make_dx("dm", "Diabetes mellitus"),
        )
        text = build_progress_note_text(ctx)
        # Subjective opens with the primary dx display.
        assert "follow-up of Diabetes mellitus" in text

    def test_primary_defaults_to_first_diagnosis_when_unset(self):
        ctx = NoteContext(
            patient_display_name="X",
            age_years=70,
            sex="male",
            today=date(2026, 4, 23),
            diagnoses=(
                _make_dx("htn", "Essential hypertension"),
                _make_dx("dm", "Diabetes mellitus"),
            ),
        )
        text = build_progress_note_text(ctx)
        assert "follow-up of Essential hypertension" in text

    def test_observations_collected_across_diagnoses(self):
        # An observation emitted under one dx should still appear in a note
        # whose primary is a different dx (notes show full clinical context).
        bp = _make_obs(
            code="85354-9",
            display="BP panel",
            components=(
                SampledComponent(
                    code=Coding(system="http://loinc.org", code="8480-6", display="SBP"),
                    value=140,
                    unit="mm[Hg]",
                    unit_code="mm[Hg]",
                ),
                SampledComponent(
                    code=Coding(system="http://loinc.org", code="8462-4", display="DBP"),
                    value=90,
                    unit="mm[Hg]",
                    unit_code="mm[Hg]",
                ),
            ),
            effective=date(2026, 4, 1),
        )
        a1c = _make_obs(
            code="4548-4",
            display="HbA1c",
            value=8.1,
            unit="%",
            effective=date(2026, 4, 5),
        )
        htn_dx = _make_dx("htn", "HTN", sampled=(bp,))
        dm_dx = _make_dx("dm", "DM", sampled=(a1c,))
        ctx = NoteContext(
            patient_display_name="X",
            age_years=70,
            sex="male",
            today=date(2026, 4, 23),
            diagnoses=(htn_dx, dm_dx),
            primary_diagnosis=htn_dx,
        )
        text = build_progress_note_text(ctx)
        # The HTN-focused note still surfaces the diabetes A1C value.
        assert "140/90" in text
        assert "8.1 %" in text

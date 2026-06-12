"""Unit tests for the LLM note renderer.

The Claude call is monkeypatched so the suite stays hermetic — no
ANTHROPIC_API_KEY required, no network.
"""

from __future__ import annotations

from datetime import date

import pytest

from parker_atlas.modules.runtime import (
    Coding,
    ConditionSpec,
    Diagnosis,
    SampledMedicationRequest,
    SampledObservation,
)
from parker_atlas.notes import (
    LLMNotesUnavailable,
    NoteContext,
    NoteStrategy,
    render_note,
)
from parker_atlas.notes import llm as llm_module


def _make_ctx() -> NoteContext:
    htn = ConditionSpec(
        id="essential_hypertension",
        code=Coding(
            system="http://snomed.info/sct",
            code="59621000",
            display="Essential hypertension",
        ),
        prevalence_by_bracket={(0, 99): 1.0},
    )
    bp = SampledObservation(
        spec_id="obs_bp",
        category="vital-signs",
        code=Coding(system="http://loinc.org", code="8480-6", display="Systolic BP"),
        value=148.0,
        unit="mmHg",
        unit_code="mm[Hg]",
        components=(),
        effective_date=date(2026, 5, 21),
        when="today",
        link_to=None,
    )
    med = SampledMedicationRequest(
        spec_id="med_lisinopril",
        medication_code=Coding(
            system="http://www.nlm.nih.gov/research/umls/rxnorm",
            code="29046",
            display="Lisinopril 10 MG Oral Tablet",
        ),
        effective_date=date(2026, 5, 21),
        reason_code=None,
        when="today",
        link_to=None,
    )
    dx = Diagnosis(
        condition=htn,
        sampled_resources=(bp, med),
        onset_date=date(2024, 1, 1),
    )
    return NoteContext(
        patient_display_name="Doe, Jane",
        age_years=62,
        sex="female",
        today=date(2026, 5, 21),
        diagnoses=(dx,),
        primary_diagnosis=dx,
    )


def test_llm_unavailable_without_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    ctx = _make_ctx()
    with pytest.raises(LLMNotesUnavailable):
        llm_module.render_llm_note(ctx)


def test_render_llm_note_assembles_markdown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    def fake_author(payload, *, model, api_key, max_tokens, temperature, provider=None):
        # Sanity-check what we hand to the model: the structured payload must
        # contain the medication and BP observation, not raw FHIR.
        assert payload["patient"]["age_years"] == 62
        assert payload["active_medications"] == ["Lisinopril 10 MG Oral Tablet"]
        assert payload["observations_most_recent"][0]["display"] == "Systolic BP"
        return (
            {
                "subjective": "Patient feels well; no chest pain or palpitations.",
                "assessment_and_plan": "1. Hypertension — continue lisinopril, recheck BP in 3 months.",
            },
            {
                "input_tokens": 100,
                "output_tokens": 40,
                "cache_read_input_tokens": 80,
                "cache_creation_input_tokens": 0,
            },
            "claude-haiku-4-5-20251001",
        )

    monkeypatch.setattr(llm_module, "_author_narrative", fake_author)

    result = llm_module.render_llm_note(_make_ctx())
    assert "## Subjective" in result.text
    assert "Patient feels well" in result.text
    assert "## Assessment & Plan" in result.text
    assert "continue lisinopril" in result.text
    # Structured sections come from the bundle, not the model — verify
    # they're present and correct.
    assert "Lisinopril 10 MG Oral Tablet" in result.text
    assert "Systolic BP" in result.text
    # Provenance footer records the model used.
    assert "claude-haiku-4-5" in result.text
    assert result.cache_read_input_tokens == 80


def test_render_note_dispatches_to_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    def fake_author(payload, *, model, api_key, max_tokens, temperature, provider=None):
        return (
            {"subjective": "stable.", "assessment_and_plan": "1. continue care."},
            {
                "input_tokens": 1,
                "output_tokens": 1,
                "cache_read_input_tokens": 0,
                "cache_creation_input_tokens": 0,
            },
            "claude-haiku-4-5-20251001",
        )

    monkeypatch.setattr(llm_module, "_author_narrative", fake_author)
    text = render_note(_make_ctx(), strategy=NoteStrategy.LLM)
    assert "# Progress Note" in text
    assert "continue care" in text


def test_llm_rejects_non_json_response(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    class _Usage:
        input_tokens = 1
        output_tokens = 1
        cache_read_input_tokens = 0
        cache_creation_input_tokens = 0

    class _Block:
        type = "text"
        text = "I cannot comply with this request."

    class _Response:
        content = [_Block()]
        usage = _Usage()
        model = "claude-haiku-4-5-20251001"

    class _Messages:
        def create(self, **_kwargs):
            return _Response()

    class _Client:
        messages = _Messages()

    class _FakeAnthropic:
        def __init__(self, **_kwargs):
            pass

        messages = _Messages()

    class _Module:
        Anthropic = _FakeAnthropic

    import sys

    monkeypatch.setitem(sys.modules, "anthropic", _Module())
    with pytest.raises(LLMNotesUnavailable):
        llm_module.render_llm_note(_make_ctx())

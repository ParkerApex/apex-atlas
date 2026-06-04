"""Tests for the dossier loader and deterministic synthesis."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from parker_atlas.author import (
    AuthorError,
    load_dossier_from_str,
    synthesize_expectation,
    synthesize_module,
)
from parker_atlas.author.dossier import DossierError
from parker_atlas.modules.runtime import load_module_from_str
from parker_atlas.validation.expectations import load_expectation_from_str

FIXTURES = Path(__file__).parent / "fixtures" / "author"
GLAUCOMA = FIXTURES / "glaucoma.dossier.yaml"


def _load_glaucoma():
    return load_dossier_from_str(GLAUCOMA.read_text(encoding="utf-8"))


class TestDossierLoader:
    def test_loads_golden_dossier(self):
        d = _load_glaucoma()
        assert d.condition == "glaucoma"
        assert d.snomed["code"] == "23986001"
        assert d.prevalence_stratify_by == "age_bracket"
        assert d.prevalence_cells["60-99"] == 0.040
        assert len(d.encounters) == 1
        assert len(d.observations) == 1
        assert len(d.medications) == 1

    def test_aggregates_distinct_citations(self):
        d = _load_glaucoma()
        cites = d.all_citations
        # Prevalence (Friedman) + AAO PPP (shared by obs + med) → deduped to 2.
        assert len(cites) == 2
        assert all(c["source"] and c["url"] for c in cites)

    def test_uncited_prevalence_rejected(self):
        raw = yaml.safe_load(GLAUCOMA.read_text(encoding="utf-8"))
        del raw["prevalence"]["citation"]
        with pytest.raises(DossierError, match="no-uncited-numbers"):
            load_dossier_from_str(yaml.safe_dump(raw))

    def test_uncited_medication_rejected(self):
        raw = yaml.safe_load(GLAUCOMA.read_text(encoding="utf-8"))
        del raw["clinical"]["medications"][0]["citation"]
        with pytest.raises(DossierError, match="no-uncited-numbers"):
            load_dossier_from_str(yaml.safe_dump(raw))

    def test_dangling_link_to_rejected(self):
        raw = yaml.safe_load(GLAUCOMA.read_text(encoding="utf-8"))
        raw["clinical"]["observations"][0]["link_to"] = "nonexistent_visit"
        with pytest.raises(DossierError, match="link_to"):
            load_dossier_from_str(yaml.safe_dump(raw))

    def test_bad_medication_fraction_rejected(self):
        raw = yaml.safe_load(GLAUCOMA.read_text(encoding="utf-8"))
        raw["clinical"]["medications"][0]["fraction"] = 1.5
        with pytest.raises(DossierError, match="fraction"):
            load_dossier_from_str(yaml.safe_dump(raw))

    def test_ungeneratable_observation_category_rejected(self):
        # The FHIR Observation builder only supports vital-signs / laboratory.
        # A dossier using e.g. "exam" must fail at author time, not generate time.
        raw = yaml.safe_load(GLAUCOMA.read_text(encoding="utf-8"))
        raw["clinical"]["observations"][0]["category"] = "exam"
        with pytest.raises(DossierError, match="not generatable"):
            load_dossier_from_str(yaml.safe_dump(raw))


class TestSynthesizeModule:
    def test_module_round_trips_through_loader(self):
        d = _load_glaucoma()
        rendered = synthesize_module(d)
        mod = load_module_from_str(rendered)
        assert mod.name == "glaucoma"
        assert len(mod.conditions) == 1
        cond = mod.conditions[0]
        assert cond.code.code == "23986001"
        # Emits: 1 encounter + 1 observation + 1 medication.
        assert len(cond.emits) == 3

    def test_prevalence_cells_survive_verbatim(self):
        d = _load_glaucoma()
        rendered = synthesize_module(d)
        mod = load_module_from_str(rendered)
        cond = mod.conditions[0]
        assert cond.prevalence_by_bracket[(60, 99)] == 0.040
        assert cond.prevalence_by_bracket[(40, 59)] == 0.012

    def test_medication_fraction_becomes_probability(self):
        d = _load_glaucoma()
        doc = yaml.safe_load(synthesize_module(d))
        med = [
            e for e in doc["conditions"][0]["emits"]
            if e["resource_type"] == "MedicationRequest"
        ][0]
        assert med["probability"] == 0.70

    def test_draft_banner_present_and_strippable(self):
        d = _load_glaucoma()
        rendered = synthesize_module(d)
        assert rendered.startswith("# DRAFT")
        # Loader ignores the comment banner.
        assert load_module_from_str(rendered).name == "glaucoma"

    def test_description_is_promotion_safe(self):
        # The description is permanent metadata that survives promotion (the
        # DRAFT banner is stripped on promote), so it must NOT carry
        # draft/lifecycle wording — only the banner does. Guards against shipped
        # modules reading "DRAFT ... pending sign-off before promotion".
        d = _load_glaucoma()
        desc = load_module_from_str(synthesize_module(d)).description
        assert "DRAFT" not in desc
        assert "before promotion" not in desc
        assert "pending" not in desc.lower()
        # It still records provenance.
        assert "atlas author" in desc
        assert "sourced" in desc.lower()

    def test_invalid_loinc_code_fails_at_author_time(self):
        raw = yaml.safe_load(GLAUCOMA.read_text(encoding="utf-8"))
        # value_range with high < low is structurally invalid for the module loader.
        raw["clinical"]["observations"][0]["value_range"] = {"low": 30, "high": 10}
        d = load_dossier_from_str(yaml.safe_dump(raw))
        with pytest.raises(AuthorError, match="failed runtime validation"):
            synthesize_module(d)


class TestSynthesizeExpectation:
    def test_expectation_round_trips_and_is_sourced(self):
        d = _load_glaucoma()
        rendered = synthesize_expectation(d)
        exp = load_expectation_from_str(rendered)
        assert exp.module == "glaucoma"
        assert exp.source.provenance == "sourced"
        assert len(exp.metrics) == 1
        m = exp.metrics[0]
        assert m.kind == "conditional_prevalence"
        assert m.stratify_by == "age_bracket"
        assert m.condition_code == "23986001"
        assert m.tolerance.kind == "wilson"
        assert m.targets[(60, 99)] == 0.040

    def test_sex_and_age_dossier_yields_sex_metric(self):
        raw = yaml.safe_load(GLAUCOMA.read_text(encoding="utf-8"))
        raw["prevalence"]["stratify_by"] = "sex_and_age"
        raw["prevalence"]["cells"] = {
            "female": {"40-59": 0.011, "60-99": 0.038},
            "male": {"40-59": 0.013, "60-99": 0.042},
        }
        d = load_dossier_from_str(yaml.safe_dump(raw))
        exp = load_expectation_from_str(synthesize_expectation(d))
        m = exp.metrics[0]
        assert m.stratify_by == "sex_and_age"
        assert m.targets_by_sex["male"][(60, 99)] == 0.042

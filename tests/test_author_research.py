"""Tests for the web_search-backed research backend.

The single network call (`_call_research_model`) is monkeypatched throughout,
so these tests never touch the SDK or the network.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

import parker_atlas.author.research as research_mod
from parker_atlas.author.research import (
    AuthorResearchUnavailable,
    research_condition,
)
from parker_atlas.cli import app

FIXTURES = Path(__file__).parent / "fixtures" / "author"
GLAUCOMA = (FIXTURES / "glaucoma.dossier.yaml").read_text(encoding="utf-8")
runner = CliRunner()


def _fake_model_reply(text):
    def _fake(condition, **kwargs):  # noqa: ANN001
        return text
    return _fake


class TestResearchCondition:
    def test_returns_validated_dossier(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.setattr(research_mod, "_call_research_model", _fake_model_reply(GLAUCOMA))
        out = research_condition("glaucoma")
        doc = yaml.safe_load(out)
        assert doc["condition"] == "glaucoma"
        assert doc["codes"]["snomed"]["code"] == "23986001"

    def test_forces_requested_condition_name(self, monkeypatch):
        # Model returns a dossier whose `condition` disagrees with the request.
        raw = yaml.safe_load(GLAUCOMA)
        raw["condition"] = "GLAUCOMA-typo"
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.setattr(
            research_mod, "_call_research_model", _fake_model_reply(yaml.safe_dump(raw))
        )
        out = research_condition("glaucoma")
        assert yaml.safe_load(out)["condition"] == "glaucoma"

    def test_strips_code_fences(self, monkeypatch):
        fenced = "```yaml\n" + GLAUCOMA + "\n```"
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.setattr(research_mod, "_call_research_model", _fake_model_reply(fenced))
        assert yaml.safe_load(research_condition("glaucoma"))["condition"] == "glaucoma"

    def test_missing_api_key_raises(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        with pytest.raises(AuthorResearchUnavailable, match="ANTHROPIC_API_KEY"):
            research_condition("glaucoma")

    def test_uncited_dossier_rejected(self, monkeypatch):
        raw = yaml.safe_load(GLAUCOMA)
        del raw["prevalence"]["citation"]  # model dropped a required citation
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.setattr(
            research_mod, "_call_research_model", _fake_model_reply(yaml.safe_dump(raw))
        )
        with pytest.raises(AuthorResearchUnavailable, match="failed validation"):
            research_condition("glaucoma")

    def test_non_yaml_reply_rejected(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.setattr(
            research_mod, "_call_research_model", _fake_model_reply("not: : valid: yaml: [")
        )
        with pytest.raises(AuthorResearchUnavailable):
            research_condition("glaucoma")


class TestResearchCli:
    def test_research_writes_dossier_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.setattr(research_mod, "_call_research_model", _fake_model_reply(GLAUCOMA))
        out = tmp_path / "glaucoma.dossier.yaml"
        result = runner.invoke(
            app, ["author", "research", "--condition", "glaucoma", "--output", str(out)]
        )
        assert result.exit_code == 0, result.output
        assert out.is_file()
        assert yaml.safe_load(out.read_text())["condition"] == "glaucoma"

    def test_research_chains_into_synthesis(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.setattr(research_mod, "_call_research_model", _fake_model_reply(GLAUCOMA))
        drafts = tmp_path / "drafts"
        result = runner.invoke(
            app,
            ["author", "research", "--condition", "glaucoma", "--draft-out", str(drafts)],
        )
        assert result.exit_code == 0, result.output
        draft = drafts / "glaucoma"
        for name in ("glaucoma.yaml", "glaucoma.expectation.yaml", "dossier.yaml", "SIGNOFF.md"):
            assert (draft / name).is_file(), f"missing {name}"

    def test_research_reports_unavailable(self, tmp_path, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        result = runner.invoke(app, ["author", "research", "--condition", "glaucoma"])
        assert result.exit_code == 1
        assert "research failed" in result.output

"""End-to-end CLI tests for the `atlas author` command family."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from parker_atlas.cli import app
from parker_atlas.modules.runtime import load_module_from_str
from parker_atlas.validation.expectations import load_expectation_from_str

FIXTURES = Path(__file__).parent / "fixtures" / "author"
GLAUCOMA = FIXTURES / "glaucoma.dossier.yaml"
runner = CliRunner()


class TestAuthorSynthesizeCli:
    def test_synthesize_writes_draft_bundle(self, tmp_path):
        out = tmp_path / "atlas-drafts"
        result = runner.invoke(
            app,
            ["author", "synthesize", "--dossier", str(GLAUCOMA), "--out", str(out)],
        )
        assert result.exit_code == 0, result.output
        draft = out / "glaucoma"
        for name in (
            "glaucoma.yaml",
            "glaucoma.expectation.yaml",
            "dossier.yaml",
            "SIGNOFF.md",
        ):
            assert (draft / name).is_file(), f"missing {name}"
        # Generated artifacts load cleanly.
        assert load_module_from_str((draft / "glaucoma.yaml").read_text()).name == "glaucoma"
        assert load_expectation_from_str(
            (draft / "glaucoma.expectation.yaml").read_text()
        ).module == "glaucoma"

    def test_synthesize_refuses_overwrite(self, tmp_path):
        out = tmp_path / "atlas-drafts"
        args = ["author", "synthesize", "--dossier", str(GLAUCOMA), "--out", str(out)]
        assert runner.invoke(app, args).exit_code == 0
        second = runner.invoke(app, args)
        assert second.exit_code == 1
        assert "already exist" in second.output
        assert runner.invoke(app, [*args, "--overwrite"]).exit_code == 0

    def test_synthesize_rejects_missing_dossier(self, tmp_path):
        result = runner.invoke(
            app,
            ["author", "synthesize", "--dossier", str(tmp_path / "nope.yaml")],
        )
        assert result.exit_code == 1
        assert "does not exist" in result.output


class TestAuthorPromoteCli:
    def test_promote_round_trip(self, tmp_path, monkeypatch):
        out = tmp_path / "atlas-drafts"
        assert runner.invoke(
            app,
            ["author", "synthesize", "--dossier", str(GLAUCOMA), "--out", str(out)],
        ).exit_code == 0
        draft = out / "glaucoma"

        # Redirect installation into a temp library so the real package is untouched.
        lib, exp = tmp_path / "lib", tmp_path / "exp"
        lib.mkdir()
        exp.mkdir()
        import parker_atlas.author.promote as promote_mod

        monkeypatch.setattr(promote_mod, "default_library_dir", lambda: lib)
        monkeypatch.setattr(promote_mod, "default_expectations_dir", lambda: exp)

        # Sign it off, then promote.
        (draft / "SIGNOFF.md").write_text("Signed-off-by: Dr. Jane Roe, MD\n", encoding="utf-8")
        result = runner.invoke(app, ["author", "promote", "--draft", str(draft)])
        assert result.exit_code == 0, result.output
        assert (lib / "glaucoma.yaml").is_file()
        assert (exp / "glaucoma.yaml").is_file()

    def test_promote_blocks_unsigned_draft(self, tmp_path, monkeypatch):
        out = tmp_path / "atlas-drafts"
        runner.invoke(
            app,
            ["author", "synthesize", "--dossier", str(GLAUCOMA), "--out", str(out)],
        )
        draft = out / "glaucoma"
        import parker_atlas.author.promote as promote_mod

        monkeypatch.setattr(promote_mod, "default_library_dir", lambda: tmp_path / "lib")
        monkeypatch.setattr(promote_mod, "default_expectations_dir", lambda: tmp_path / "exp")
        result = runner.invoke(app, ["author", "promote", "--draft", str(draft)])
        assert result.exit_code == 1
        assert "not signed off" in result.output


class TestAuthorResearchStub:
    def test_research_is_stub(self):
        result = runner.invoke(app, ["author", "research", "--condition", "glaucoma"])
        assert result.exit_code == 2
        # Rich may wrap the message, so match a single unwrapped token.
        assert "implemented" in result.output

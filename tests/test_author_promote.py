"""Tests for `promote_draft` and its sign-off gate."""

from __future__ import annotations

from pathlib import Path

import pytest

from parker_atlas.author import (
    load_dossier_from_str,
    synthesize_expectation,
    synthesize_module,
)
from parker_atlas.author.promote import PromotionError, promote_draft, signoff_name
from parker_atlas.modules.runtime import load_module_from_str
from parker_atlas.validation.expectations import load_expectation_from_str

FIXTURES = Path(__file__).parent / "fixtures" / "author"
GLAUCOMA = FIXTURES / "glaucoma.dossier.yaml"


def _make_draft(tmp_path: Path, *, signed: bool) -> Path:
    d = load_dossier_from_str(GLAUCOMA.read_text(encoding="utf-8"))
    draft_dir = tmp_path / "drafts" / d.condition
    draft_dir.mkdir(parents=True)
    (draft_dir / f"{d.condition}.yaml").write_text(synthesize_module(d), encoding="utf-8")
    (draft_dir / f"{d.condition}.expectation.yaml").write_text(
        synthesize_expectation(d), encoding="utf-8"
    )
    signoff = "Signed-off-by: Dr. Jane Roe, MD\n" if signed else "Signed-off-by: \n"
    (draft_dir / "SIGNOFF.md").write_text(signoff, encoding="utf-8")
    return draft_dir


class TestSignoffGate:
    def test_unsigned_draft_reads_as_none(self, tmp_path):
        draft = _make_draft(tmp_path, signed=False)
        assert signoff_name(draft) is None

    def test_signed_draft_reads_name(self, tmp_path):
        draft = _make_draft(tmp_path, signed=True)
        assert signoff_name(draft) == "Dr. Jane Roe, MD"

    def test_promote_refuses_unsigned(self, tmp_path):
        draft = _make_draft(tmp_path, signed=False)
        with pytest.raises(PromotionError, match="not signed off"):
            promote_draft(
                draft,
                library_dir=tmp_path / "lib",
                expectations_dir=tmp_path / "exp",
            )

    def test_force_overrides_signoff(self, tmp_path):
        draft = _make_draft(tmp_path, signed=False)
        mod_path, exp_path = promote_draft(
            draft,
            library_dir=tmp_path / "lib",
            expectations_dir=tmp_path / "exp",
            force=True,
        )
        assert mod_path.is_file() and exp_path.is_file()


class TestPromoteInstall:
    def test_promotes_and_revalidates(self, tmp_path):
        draft = _make_draft(tmp_path, signed=True)
        lib, exp = tmp_path / "lib", tmp_path / "exp"
        mod_path, exp_path = promote_draft(draft, library_dir=lib, expectations_dir=exp)

        assert mod_path == lib / "glaucoma.yaml"
        assert exp_path == exp / "glaucoma.yaml"
        # Promoted files must still load cleanly.
        assert load_module_from_str(mod_path.read_text()).name == "glaucoma"
        assert load_expectation_from_str(exp_path.read_text()).module == "glaucoma"

    def test_draft_banner_stripped_on_promote(self, tmp_path):
        draft = _make_draft(tmp_path, signed=True)
        mod_path, _ = promote_draft(
            draft, library_dir=tmp_path / "lib", expectations_dir=tmp_path / "exp"
        )
        assert not mod_path.read_text().startswith("# DRAFT")

    def test_refuses_overwrite_without_flag(self, tmp_path):
        draft = _make_draft(tmp_path, signed=True)
        lib, exp = tmp_path / "lib", tmp_path / "exp"
        promote_draft(draft, library_dir=lib, expectations_dir=exp)
        with pytest.raises(PromotionError, match="already exist"):
            promote_draft(draft, library_dir=lib, expectations_dir=exp)
        # With overwrite it succeeds.
        promote_draft(draft, library_dir=lib, expectations_dir=exp, overwrite=True)

    def test_missing_files_rejected(self, tmp_path):
        draft = tmp_path / "drafts" / "glaucoma"
        draft.mkdir(parents=True)
        with pytest.raises(PromotionError, match="missing"):
            promote_draft(draft, library_dir=tmp_path / "lib", expectations_dir=tmp_path / "exp", force=True)

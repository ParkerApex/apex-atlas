"""
Promote a clinician-reviewed draft into the bundled library.

`promote_draft` is intentionally thin: it re-validates the reviewed draft
module and expectation through the real loaders, enforces the sign-off gate,
strips the DRAFT banner, and installs the two files into the shipping
locations. It never edits the dossier or the module body — promotion is a
move, not an edit, so the reviewed bytes are what ships.
"""

from __future__ import annotations

import re
from pathlib import Path

from parker_atlas.author.synthesize import DRAFT_BANNER
from parker_atlas.modules.runtime import ModuleError, load_module_from_str
from parker_atlas.validation.expectations import (
    ExpectationError,
    load_expectation_from_str,
)

# A draft is promotable once SIGNOFF.md carries a non-empty `Signed-off-by:`
# value. Synthesis writes the line with an empty value; a reviewer fills it in.
# Horizontal-whitespace only (NOT \s, which spans newlines) so an empty
# `Signed-off-by:` line never absorbs the following line's text as the value.
SIGNOFF_PATTERN = re.compile(
    r"^[ \t]*signed-off-by:[ \t]*(?P<who>\S.*?)[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)


class PromotionError(ValueError):
    """Raised when a draft cannot be promoted."""


def _package_root() -> Path:
    # parker_atlas/author/promote.py → parker_atlas/
    return Path(__file__).resolve().parents[1]


def default_library_dir() -> Path:
    return _package_root() / "modules" / "library"


def default_expectations_dir() -> Path:
    return _package_root() / "validation" / "expectations" / "library"


def signoff_name(draft_dir: Path) -> str | None:
    """Return the reviewer recorded in SIGNOFF.md, or None if unsigned."""
    signoff = draft_dir / "SIGNOFF.md"
    if not signoff.is_file():
        return None
    match = SIGNOFF_PATTERN.search(signoff.read_text(encoding="utf-8"))
    if not match:
        return None
    who = match.group("who").strip()
    # Treat the unfilled placeholder as unsigned.
    if not who or who in {"_", "__", "___", "TODO", "TBD", "(name)", "<name>"}:
        return None
    return who


def promote_draft(
    draft_dir: Path,
    *,
    library_dir: Path | None = None,
    expectations_dir: Path | None = None,
    overwrite: bool = False,
    force: bool = False,
) -> tuple[Path, Path]:
    """Install a reviewed draft into the library. Returns (module_path, expectation_path)."""
    draft_dir = Path(draft_dir)
    if not draft_dir.is_dir():
        raise PromotionError(f"draft directory does not exist: {draft_dir}")

    condition = draft_dir.name
    module_src = draft_dir / f"{condition}.yaml"
    expectation_src = draft_dir / f"{condition}.expectation.yaml"
    if not module_src.is_file():
        raise PromotionError(f"draft is missing {module_src.name} in {draft_dir}")
    if not expectation_src.is_file():
        raise PromotionError(f"draft is missing {expectation_src.name} in {draft_dir}")

    if not force and signoff_name(draft_dir) is None:
        raise PromotionError(
            f"draft {condition!r} is not signed off. Fill in the `Signed-off-by:` "
            f"line in {draft_dir / 'SIGNOFF.md'} (or pass force=True to override)."
        )

    module_text = module_src.read_text(encoding="utf-8")
    expectation_text = expectation_src.read_text(encoding="utf-8")

    # Re-validate the reviewed bytes; refuse to ship anything that won't load.
    try:
        module = load_module_from_str(module_text)
    except ModuleError as exc:
        raise PromotionError(f"draft module failed validation: {exc}") from exc
    try:
        load_expectation_from_str(expectation_text)
    except ExpectationError as exc:
        raise PromotionError(f"draft expectation failed validation: {exc}") from exc

    if module.name != condition:
        raise PromotionError(
            f"module name {module.name!r} does not match draft directory {condition!r}"
        )

    # Strip the DRAFT banner — the promoted module is no longer a draft.
    if module_text.startswith(DRAFT_BANNER):
        module_text = module_text[len(DRAFT_BANNER) :]

    library_dir = library_dir or default_library_dir()
    expectations_dir = expectations_dir or default_expectations_dir()
    module_dst = library_dir / f"{condition}.yaml"
    expectation_dst = expectations_dir / f"{condition}.yaml"

    existing = [p for p in (module_dst, expectation_dst) if p.exists()]
    if existing and not overwrite:
        raise PromotionError(
            f"destination files already exist: {', '.join(str(p) for p in existing)}. "
            f"Pass overwrite=True to replace."
        )

    library_dir.mkdir(parents=True, exist_ok=True)
    expectations_dir.mkdir(parents=True, exist_ok=True)
    module_dst.write_text(module_text, encoding="utf-8")
    expectation_dst.write_text(expectation_text, encoding="utf-8")
    return module_dst, expectation_dst

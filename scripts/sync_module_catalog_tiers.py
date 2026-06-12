#!/usr/bin/env python3
"""Refresh module catalog tiers from bundled fidelity expectations and scorecard."""

from __future__ import annotations

import re
from pathlib import Path

from parker_atlas.validation.expectations import list_bundled_expectations
from parker_atlas.validation.gtm import GTM_EXCLUDED_MODULES, GTM_HEADLINE_MODULES

REPO = Path(__file__).resolve().parents[1]
CATALOG = REPO / "docs" / "module-catalog.md"
SCORECARD = REPO / "docs" / "fidelity-scorecard.md"


def _scorecard_status() -> dict[str, str]:
    out: dict[str, str] = {}
    if not SCORECARD.is_file():
        return out
    for line in SCORECARD.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|") or line.startswith("| Module"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) >= 7 and cells[0] not in {"---", "Module"}:
            out[cells[0]] = cells[-1]
    return out


def _tier_for(module: str, *, has_expectation: bool, scorecard: dict[str, str]) -> int:
    if module in GTM_EXCLUDED_MODULES and module == "glaucoma":
        return 3
    if module in GTM_EXCLUDED_MODULES:
        return 2
    if module in GTM_HEADLINE_MODULES and has_expectation:
        status = scorecard.get(module, "")
        if "pass" in status:
            return 1
    if has_expectation:
        status = scorecard.get(module, "")
        if "pass" in status:
            return 2
    return 2


def main() -> None:
    expectations = set(list_bundled_expectations())
    scorecard = _scorecard_status()
    text = CATALOG.read_text(encoding="utf-8")
    lines = text.splitlines()
    out_lines: list[str] = []
    in_table = False
    for line in lines:
        if line.strip() == "## Current Library":
            in_table = True
            out_lines.append(line)
            continue
        if in_table and line.startswith("## "):
            in_table = False
        if in_table and line.startswith("| ") and not line.startswith("| Module"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) >= 5 and cells[0] not in {"---"}:
                mod = cells[0]
                has_exp = mod in expectations
                tier = _tier_for(mod, has_expectation=has_exp, scorecard=scorecard)
                fidelity = "Sourced" if has_exp else "Pending"
                review = (
                    "Pending licensed clinician sign-off"
                    if mod in GTM_EXCLUDED_MODULES
                    else "Internal technical review"
                )
                cells[2] = str(tier)
                cells[3] = fidelity
                cells[4] = review
                out_lines.append("| " + " | ".join(cells) + " |")
                continue
        out_lines.append(line)

    new_text = "\n".join(out_lines)
    new_text = re.sub(
        r"\*Last updated: .*\*",
        "*Last updated: 2026-06-12*",
        new_text,
        count=1,
    )
    CATALOG.write_text(new_text + "\n", encoding="utf-8")
    print(f"Updated {CATALOG}")


if __name__ == "__main__":
    main()

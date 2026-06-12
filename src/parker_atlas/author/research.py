"""
Autonomous dossier research via an LLM + the web_search server tool.

`research_condition` asks the configured research model to research one clinical condition against
public, authoritative US sources (NHANES/CDC/SEER/published meta-analyses,
ICD-10/SNOMED/LOINC/RxNorm terminologies) using the server-side web_search
tool, and to emit a dossier YAML matching the schema enforced by
`author/dossier.py`. The result is validated with `load_dossier_from_str`
before it is returned, so a research pass that omits a citation or produces a
structurally bad dossier fails here rather than downstream.

This is the Phase-2 backend behind `atlas author research`. The dossier
contract is identical to the hand-/skill-authored path, so nothing downstream
(synthesis, promotion, generation, validation) changes.

Failure mode mirrors `notes/llm.py`: if the `anthropic` SDK is missing or no
API key is present, `AuthorResearchUnavailable` is raised with a clear message.
The single network call is isolated in `_call_research_model` so tests can
monkeypatch it with a fake and never touch the network.
"""

from __future__ import annotations

import os

import yaml

from parker_atlas.author.dossier import (
    OBSERVATION_CATEGORIES,
    DossierError,
    load_dossier_from_str,
)

DEFAULT_RESEARCH_MODEL = "claude-sonnet-4-6"
"""Sonnet 4.6 — strong enough for grounded web research + structured
extraction, far cheaper than Opus for a one-shot dossier. Override with
--model for a reference-grade pass."""

DEFAULT_MAX_WEB_SEARCHES = 8


class AuthorResearchUnavailable(RuntimeError):
    """Raised when the research backend is requested but cannot be served."""


def _system_prompt() -> str:
    cats = " | ".join(OBSERVATION_CATEGORIES)
    return f"""\
You are a clinical epidemiology research assistant building a SYNTHETIC-patient
generation module. You research one condition and emit a structured "dossier"
that downstream tooling turns into a synthetic-data module. No real patient is
ever depicted.

Use the web_search tool to find AUTHORITATIVE, PUBLIC US sources:
- Prevalence by age (and sex when the source reports it): NHANES, CDC Data
  Briefs / WONDER, SEER, USRDS, or peer-reviewed prevalence meta-analyses.
- Correct terminology codes: SNOMED CT for the condition, ICD-10-CM diagnosis
  codes, LOINC for any lab/vital observation, RxNorm for medications.
- First-line treatment and the approximate share of diagnosed patients who
  receive it (guidelines, e.g. specialty society practice patterns).

HARD RULES — the dossier is rejected if violated:
- EVERY numeric claim carries a `citation` with at least a `source` (prefer a
  real `url` and `table`/section). This includes prevalence cells, each
  observation value_range, each medication fraction, and each progression.
- Do NOT invent codes or rates. If you cannot find a sourced number, omit that
  element rather than guessing.
- Observation `category` MUST be one of: {cats}.
- Use only credentialed-data-free public sources (never MIMIC/UK Biobank/etc.).

Output ONLY the dossier as YAML — no prose, no code fences — matching exactly:

condition: <snake_case module name>
version: 0.1.0
generated:
  method: web_search
  model: <the model you are>
  accessed: "<ISO date you ran the search>"
codes:
  snomed: {{system: http://snomed.info/sct, code: "<id>", display: "<term>"}}
  icd10:
    - {{code: "<icd10>", display: "<term>"}}
prevalence:
  stratify_by: age_bracket        # or sex_and_age
  cells:                          # {{bracket: rate}} OR {{female:{{...}}, male:{{...}}}}
    "0-39": <rate>
    "40-59": <rate>
    "60-99": <rate>
  citation: {{source: "...", url: "...", table: "...", accessed: "...", summary: "..."}}
onset_age: {{min: <int>, max: <int>}}
clinical:
  encounters:
    - spec_id: <id>
      class: AMB
      type: {{system: http://snomed.info/sct, code: "...", display: "..."}}
  observations:
    - spec_id: <id>
      category: laboratory        # {cats}
      link_to: <encounter spec_id>
      loinc: {{system: http://loinc.org, code: "...", display: "..."}}
      value_range: {{low: <n>, high: <n>, precision: <int>}}
      unit: "<ucum>"
      citation: {{source: "...", url: "...", summary: "..."}}
  medications:
    - spec_id: <id>
      medication: {{system: http://www.nlm.nih.gov/research/umls/rxnorm, code: "...", display: "..."}}
      fraction: <0..1>
      link_to: <encounter spec_id>
      citation: {{source: "...", url: "...", summary: "..."}}
progressions: []                  # optional one-hop; each needs a citation
notes: "<reviewer caveats>"
"""


def _call_research_model(
    condition: str,
    *,
    model: str,
    api_key: str,
    max_tokens: int,
    max_web_searches: int,
) -> str:
    """Run the web_search-grounded research call and return the raw text reply.

    Isolated so tests can monkeypatch it without the SDK or the network.
    """
    try:
        import anthropic  # type: ignore[import-not-found]
    except ImportError as exc:
        raise AuthorResearchUnavailable(
            "Autonomous research requires the 'anthropic' package. "
            'Install with: pip install -e ".[llm]"'
        ) from exc

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=0.0,
        system=[{"type": "text", "text": _system_prompt()}],
        tools=[
            {
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": max_web_searches,
            }
        ],
        messages=[
            {
                "role": "user",
                "content": (
                    f"Research the clinical condition '{condition}' and produce its "
                    f"dossier. Use the snake_case module name '{condition}'."
                ),
            }
        ],
    )
    text_blocks = [b.text for b in response.content if getattr(b, "type", "") == "text"]
    return "".join(text_blocks).strip()


def _strip_fences(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        # Drop an optional leading language tag line (```yaml / ```yml).
        first_nl = text.find("\n")
        if first_nl != -1 and text[:first_nl].strip().lower() in ("yaml", "yml"):
            text = text[first_nl + 1 :]
    return text.strip()


def research_condition(
    condition: str,
    *,
    model: str = DEFAULT_RESEARCH_MODEL,
    api_key: str | None = None,
    max_tokens: int = 4096,
    max_web_searches: int = DEFAULT_MAX_WEB_SEARCHES,
) -> str:
    """Research `condition` and return a validated dossier YAML string.

    Raises `AuthorResearchUnavailable` if the SDK/key is missing or the model
    cannot produce a valid dossier. The returned YAML has its `condition`
    forced to the requested snake_case name so the downstream draft filename is
    deterministic.
    """
    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise AuthorResearchUnavailable(
            "Autonomous research requires ANTHROPIC_API_KEY in the environment "
            "(or pass api_key= explicitly)."
        )

    raw = _call_research_model(
        condition,
        model=model,
        api_key=key,
        max_tokens=max_tokens,
        max_web_searches=max_web_searches,
    )
    text = _strip_fences(raw)

    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise AuthorResearchUnavailable(
            f"research model returned non-YAML; refusing to write a dossier. "
            f"First 200 chars: {text[:200]!r}"
        ) from exc
    if not isinstance(data, dict):
        raise AuthorResearchUnavailable(
            "research model did not return a YAML mapping at the top level."
        )

    # Force the module name so the draft filename is deterministic.
    data["condition"] = condition
    rendered = yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=100)

    # Validate against the dossier contract — same gate as the manual path.
    try:
        load_dossier_from_str(rendered)
    except DossierError as exc:
        raise AuthorResearchUnavailable(
            f"researched dossier failed validation: {exc}"
        ) from exc
    return rendered

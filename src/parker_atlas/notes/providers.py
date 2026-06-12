"""LLM provider backends for clinical note authoring."""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from typing import Any


class LLMProvider(ABC):
    """Minimal interface for narrative JSON generation."""

    @abstractmethod
    def complete_json(
        self,
        *,
        system_prompt: str,
        user_payload: dict[str, Any],
        model: str,
        max_tokens: int,
        temperature: float,
    ) -> tuple[dict[str, str], dict[str, int], str]:
        """Return (parsed_json, usage_dict, model_id)."""


class AnthropicProvider(LLMProvider):
    def complete_json(
        self,
        *,
        system_prompt: str,
        user_payload: dict[str, Any],
        model: str,
        max_tokens: int,
        temperature: float,
    ) -> tuple[dict[str, str], dict[str, int], str]:
        try:
            import anthropic  # type: ignore[import-not-found]
        except ImportError as exc:
            from parker_atlas.notes.llm import LLMNotesUnavailable

            raise LLMNotesUnavailable(
                "LLM note authoring requires the 'anthropic' package. "
                'Install with: pip install -e ".[llm]"'
            ) from exc

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=[
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[
                {
                    "role": "user",
                    "content": [{"type": "text", "text": json.dumps(user_payload, indent=2)}],
                }
            ],
        )
        return _parse_json_response(response)


class OpenAIProvider(LLMProvider):
    def complete_json(
        self,
        *,
        system_prompt: str,
        user_payload: dict[str, Any],
        model: str,
        max_tokens: int,
        temperature: float,
    ) -> tuple[dict[str, str], dict[str, int], str]:
        try:
            import openai  # type: ignore[import-not-found]
        except ImportError as exc:
            from parker_atlas.notes.llm import LLMNotesUnavailable

            raise LLMNotesUnavailable(
                "OpenAI provider requires the 'openai' package. "
                'Install with: pip install -e ".[llm]"'
            ) from exc

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            from parker_atlas.notes.llm import LLMNotesUnavailable

            raise LLMNotesUnavailable(
                "OpenAI provider requires OPENAI_API_KEY in the environment."
            )
        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_payload, indent=2)},
            ],
        )
        choice = response.choices[0].message.content or ""
        parsed = json.loads(choice)
        if not isinstance(parsed, dict):
            from parker_atlas.notes.llm import LLMNotesUnavailable

            raise LLMNotesUnavailable("OpenAI returned non-object JSON.")
        usage = response.usage
        usage_dict = {
            "input_tokens": getattr(usage, "prompt_tokens", 0) or 0,
            "output_tokens": getattr(usage, "completion_tokens", 0) or 0,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
        }
        return parsed, usage_dict, response.model or model


def _parse_json_response(response: Any) -> tuple[dict[str, str], dict[str, int], str]:
    from parker_atlas.notes.llm import LLMNotesUnavailable

    text_blocks = [b.text for b in response.content if getattr(b, "type", "") == "text"]
    raw = "".join(text_blocks).strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json\n"):
            raw = raw[len("json\n") :]
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LLMNotesUnavailable(
            f"LLM returned non-JSON narrative; refusing to write a note. "
            f"First 200 chars: {raw[:200]!r}"
        ) from exc
    if not isinstance(parsed, dict) or not {
        "subjective",
        "assessment_and_plan",
    }.issubset(parsed):
        raise LLMNotesUnavailable(
            "LLM JSON missing required keys 'subjective' / 'assessment_and_plan'."
        )
    usage = {
        "input_tokens": getattr(response.usage, "input_tokens", 0) or 0,
        "output_tokens": getattr(response.usage, "output_tokens", 0) or 0,
        "cache_read_input_tokens": getattr(response.usage, "cache_read_input_tokens", 0)
        or 0,
        "cache_creation_input_tokens": getattr(
            response.usage, "cache_creation_input_tokens", 0
        )
        or 0,
    }
    return parsed, usage, response.model


DEFAULT_OPENAI_MODEL = "gpt-4o-mini"


def resolve_provider(name: str | None = None) -> LLMProvider:
    """Select provider from ATLAS_LLM_PROVIDER (anthropic|openai)."""
    chosen = (name or os.environ.get("ATLAS_LLM_PROVIDER", "anthropic")).strip().lower()
    if chosen == "openai":
        return OpenAIProvider()
    if chosen == "anthropic":
        return AnthropicProvider()
    from parker_atlas.notes.llm import LLMNotesUnavailable

    raise LLMNotesUnavailable(
        f"Unknown ATLAS_LLM_PROVIDER {chosen!r}; expected 'anthropic' or 'openai'."
    )

"""
Progression CSV → progressions-overlay YAML.

Input shape:

- `input.csv`: one row per (from, to) progression with `after_years`,
  `probability` (and optionally `source_note` for audit).
- `metadata.yaml`: module / version / source (provenance + citations).

Output: a fully-formed progressions-overlay YAML string. The output is
round-tripped through `apply_progressions_overlay` against the matching
bundled module before being returned, so malformed rates fail at ingest
time rather than at module-load time.

Ingest refuses `provenance: placeholder`: the whole point of ingest is
to attach provenance + citations to numbers that came from an external
source. Hand-authored placeholder rates belong inline in the module
YAML.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import yaml

from parker_atlas.modules.runtime import (
    ModuleError,
    apply_progressions_overlay,
    load_module,
)


class IngestionError(ValueError):
    """Raised when an ingestion run has malformed inputs."""


REQUIRED_CSV_COLUMNS = ("from", "to", "after_years", "probability")
ALLOWED_INGEST_PROVENANCE = ("sourced", "verified")


def ingest_progression(csv_path: Path, metadata_path: Path) -> str:
    """Build a validated progressions-overlay YAML string from CSV + metadata."""
    meta = _read_yaml(metadata_path)
    _validate_metadata(meta)
    rows = _read_csv(csv_path)
    progressions = _build_progressions(rows)

    overlay = {
        "module": str(meta["module"]),
        "version": str(meta.get("version", "0.1.0")),
        "source": _build_source(meta),
        "progressions": progressions,
    }
    rendered = _dump_yaml(overlay)

    # Round-trip through the runtime: load the bundled module, apply the
    # overlay, and surface any structural mismatch (unknown from/to pairs,
    # invalid rates) as IngestionError rather than a load-time crash later.
    try:
        module = load_module(str(meta["module"]))
    except ModuleError as exc:
        raise IngestionError(
            f"cannot validate overlay against bundled module {meta['module']!r}: {exc}"
        ) from exc
    try:
        apply_progressions_overlay(module, rendered)
    except ModuleError as exc:
        raise IngestionError(
            f"generated overlay failed module-load validation: {exc}"
        ) from exc

    return rendered


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise IngestionError(f"cannot read metadata file {path}: {exc}") from exc
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise IngestionError(f"invalid metadata YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise IngestionError("metadata must be a YAML mapping at the top level")
    return data


def _read_csv(path: Path) -> list[dict[str, str]]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise IngestionError(f"cannot read CSV file {path}: {exc}") from exc
    reader = csv.DictReader(text.splitlines())
    fields = reader.fieldnames or []
    missing = [c for c in REQUIRED_CSV_COLUMNS if c not in fields]
    if missing:
        raise IngestionError(f"CSV missing required columns: {missing}")
    rows = [{k: (v or "").strip() for k, v in row.items()} for row in reader]
    if not rows:
        raise IngestionError("CSV has no data rows")
    return rows


def _validate_metadata(meta: dict[str, Any]) -> None:
    for required in ("module", "source"):
        if required not in meta:
            raise IngestionError(f"metadata missing required key: {required}")
    src = meta["source"]
    if not isinstance(src, dict):
        raise IngestionError("metadata.source must be a mapping")
    if "provenance" not in src:
        raise IngestionError("metadata.source must declare 'provenance'")
    if src["provenance"] not in ALLOWED_INGEST_PROVENANCE:
        raise IngestionError(
            f"ingest requires provenance of 'sourced' or 'verified'; got "
            f"{src['provenance']!r}. Hand-authored placeholder rates belong "
            f"inline in the module YAML."
        )


def _build_source(meta: dict[str, Any]) -> dict[str, Any]:
    src = meta["source"]
    out: dict[str, Any] = {
        "name": str(src.get("name", "")),
        "provenance": src["provenance"],
    }
    for key in ("url", "note"):
        if src.get(key):
            out[key] = str(src[key])
    citations = src.get("citations") or []
    if citations:
        out["citations"] = citations
    return out


def _build_progressions(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    seen_pairs: set[tuple[str, str]] = set()
    for i, row in enumerate(rows, start=2):
        for req in REQUIRED_CSV_COLUMNS:
            if not row.get(req):
                raise IngestionError(f"CSV line {i}: missing required value for {req}")
        try:
            after_years = int(row["after_years"])
        except ValueError as exc:
            raise IngestionError(
                f"CSV line {i}: after_years must be an integer, got {row['after_years']!r}"
            ) from exc
        if after_years < 0:
            raise IngestionError(
                f"CSV line {i}: after_years {after_years} must be >= 0"
            )
        try:
            probability = float(row["probability"])
        except ValueError as exc:
            raise IngestionError(
                f"CSV line {i}: probability must be a float, got {row['probability']!r}"
            ) from exc
        if not 0.0 <= probability <= 1.0:
            raise IngestionError(
                f"CSV line {i}: probability {probability} must be in [0, 1]"
            )
        pair = (row["from"], row["to"])
        if pair in seen_pairs:
            raise IngestionError(
                f"CSV line {i}: duplicate (from={pair[0]}, to={pair[1]}) — each "
                f"progression target should appear exactly once"
            )
        seen_pairs.add(pair)
        output.append(
            {
                "from": row["from"],
                "to": row["to"],
                "after_years": after_years,
                "probability": probability,
            }
        )
    return output


class _NoAliasDumper(yaml.SafeDumper):
    """SafeDumper that never emits anchors/aliases, even when sub-trees repeat."""

    def ignore_aliases(self, _data: Any) -> bool:
        return True


def _dump_yaml(obj: Any) -> str:
    return yaml.dump(
        obj,
        Dumper=_NoAliasDumper,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
        width=100,
    )

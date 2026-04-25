"""
Prevalence CSV → fidelity expectation YAML.

Input shape:

- `input.csv`: one row per (metric_id, bracket, [sex]) with `prevalence`
  (and optionally `n`, `source_note` for audit).
- `metadata.yaml`: module / version / source (provenance + citations) /
  tolerance policy / per-metric terminology codes.

Output: a fully-formed expectation YAML string. The output is
round-tripped through `load_expectation_from_str` before being
returned, so malformed metadata fails at ingest time rather than at
`atlas validate --cohort` time.

Ingest refuses `provenance: placeholder`: the whole point of ingest is
to attach provenance + citations to numbers that came from an external
source. Placeholder expectations are authored by hand.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

from parker_atlas.validation.expectations import (
    SEX_STRATA,
    ExpectationError,
    load_expectation_from_str,
)


class IngestionError(ValueError):
    """Raised when an ingestion run has malformed inputs."""


REQUIRED_CSV_COLUMNS = ("metric_id", "bracket", "prevalence")
ALLOWED_INGEST_PROVENANCE = ("sourced", "verified")


def ingest_prevalence(csv_path: Path, metadata_path: Path) -> str:
    """Build a validated expectation YAML string from CSV + metadata."""
    meta = _read_yaml(metadata_path)
    _validate_metadata(meta)
    rows = _read_csv(csv_path)
    metrics = _build_metrics(rows, meta)

    expectation = {
        "module": str(meta["module"]),
        "version": str(meta.get("version", "0.1.0")),
        "source": _build_source(meta),
        "metrics": metrics,
    }
    rendered = _dump_yaml(expectation)

    # Round-trip through the runtime loader so bad output fails here, not later.
    try:
        load_expectation_from_str(rendered)
    except ExpectationError as exc:
        raise IngestionError(
            f"generated expectation failed runtime validation: {exc}"
        ) from exc

    return rendered


# -- Parsing helpers ---------------------------------------------------------


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
    for required in ("module", "source", "tolerance", "metrics"):
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
            f"{src['provenance']!r}. Placeholder expectations should be authored "
            f"by hand in the library directory."
        )
    tol = meta["tolerance"]
    if not isinstance(tol, dict) or "kind" not in tol:
        raise IngestionError("metadata.tolerance must be a mapping with 'kind'")
    if not isinstance(meta["metrics"], dict):
        raise IngestionError(
            "metadata.metrics must be a mapping of metric_id → {condition_code, condition_system}"
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


def _build_metrics(
    rows: list[dict[str, str]], meta: dict[str, Any]
) -> list[dict[str, Any]]:
    metrics_meta = meta["metrics"]
    tolerance = meta["tolerance"]

    by_metric: dict[str, list[dict[str, str]]] = defaultdict(list)
    for i, row in enumerate(rows, start=2):
        for req in REQUIRED_CSV_COLUMNS:
            if not row.get(req):
                raise IngestionError(f"CSV line {i}: missing required value for {req}")
        by_metric[row["metric_id"]].append(row)

    output: list[dict[str, Any]] = []
    for metric_id in sorted(by_metric):
        metric_rows = by_metric[metric_id]
        mm = metrics_meta.get(metric_id)
        if mm is None:
            raise IngestionError(
                f"metadata.metrics missing entry for metric {metric_id!r} "
                f"(CSV has {len(metric_rows)} rows referencing it)"
            )
        for required in ("condition_code", "condition_system"):
            if not mm.get(required):
                raise IngestionError(
                    f"metadata.metrics.{metric_id} missing {required}"
                )

        sexes = {row.get("sex", "") for row in metric_rows}
        sexes.discard("")
        if sexes and sexes - set(SEX_STRATA):
            raise IngestionError(
                f"metric {metric_id}: invalid sex values {sorted(sexes)}; "
                f"choices: {list(SEX_STRATA)}"
            )

        if sexes:
            if any(not row.get("sex") for row in metric_rows):
                raise IngestionError(
                    f"metric {metric_id}: some rows have sex, others don't — "
                    f"ingest requires all-or-none per metric"
                )
            targets: dict[str, Any] = {}
            for sex in SEX_STRATA:
                sex_rows = [r for r in metric_rows if r.get("sex") == sex]
                if sex_rows:
                    targets[sex] = {
                        r["bracket"]: float(r["prevalence"]) for r in sex_rows
                    }
            stratify_by = "sex_and_age"
        else:
            targets = {r["bracket"]: float(r["prevalence"]) for r in metric_rows}
            stratify_by = "age_bracket"

        output.append(
            {
                "id": metric_id,
                "kind": "conditional_prevalence",
                "condition_code": str(mm["condition_code"]),
                "condition_system": str(mm["condition_system"]),
                "stratify_by": stratify_by,
                "tolerance": tolerance,
                "targets": targets,
            }
        )

    # Emit-presence metrics live entirely in metadata (no CSV rows). They
    # get appended in declaration order after the prevalence metrics.
    for em in meta.get("emit_metrics") or []:
        for required in ("id", "condition_code", "emit_resource_type", "target"):
            if not em.get(required):
                raise IngestionError(
                    f"emit_metrics: missing required key {required!r} in {em!r}"
                )
        target = float(em["target"])
        if not 0.0 <= target <= 1.0:
            raise IngestionError(
                f"emit_metrics.{em['id']}: target {target} must be in [0, 1]"
            )
        rendered: dict[str, Any] = {
            "id": str(em["id"]),
            "kind": "emit_presence_rate",
            "condition_code": str(em["condition_code"]),
            "condition_system": str(em.get("condition_system", "http://snomed.info/sct")),
            "tolerance": tolerance,
            "emit_resource_type": str(em["emit_resource_type"]),
            "target": target,
        }
        if em.get("emit_code"):
            rendered["emit_code"] = str(em["emit_code"])
        if em.get("emit_code_system"):
            rendered["emit_code_system"] = str(em["emit_code_system"])
        output.append(rendered)

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

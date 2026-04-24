"""
Demographic reference CSV → bundled references/tables/*.csv.

Mirrors `ingest_prevalence` for the demographic-distribution axis. A
user extracts joint or marginal ACS tables into one of the expected
CSV shapes (age_sex / race / ethnicity), writes a small metadata YAML
carrying provenance + citations, and runs `atlas ingest demographics`.
The command validates both files, writes the validated CSV to its
target location, and drops a sibling `<table>.provenance.yaml`
carrying the citation chain.

CSV shapes are the same as the bundled files read by
`parker_atlas.references`:
- `age_sex`:   age_low, age_high, sex, weight
- `race`:      code, display, weight
- `ethnicity`: code, display, weight
"""

from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path
from typing import Any

import yaml

from parker_atlas.ingest.prevalence import IngestionError, _NoAliasDumper

SUPPORTED_TABLES = ("age_sex", "race", "ethnicity")
ALLOWED_INGEST_PROVENANCE = ("sourced", "verified")
SEX_STRATA = ("female", "male")

_TABLE_SCHEMAS: dict[str, tuple[str, ...]] = {
    "age_sex": ("age_low", "age_high", "sex", "weight"),
    "race": ("code", "display", "weight"),
    "ethnicity": ("code", "display", "weight"),
}


def ingest_demographics(
    csv_path: Path, metadata_path: Path
) -> tuple[str, str, str]:
    """Validate inputs and return (table_name, csv_content, provenance_yaml)."""
    meta = _read_yaml(metadata_path)
    _validate_metadata(meta)
    table = str(meta["table"])
    csv_content = _read_and_validate_csv(csv_path, table)
    provenance = _build_provenance(meta)
    return table, csv_content, provenance


# -- Metadata ---------------------------------------------------------------


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


def _validate_metadata(meta: dict[str, Any]) -> None:
    for required in ("table", "source"):
        if required not in meta:
            raise IngestionError(f"metadata missing required key: {required}")
    if meta["table"] not in SUPPORTED_TABLES:
        raise IngestionError(
            f"unknown table {meta['table']!r}; choices: {list(SUPPORTED_TABLES)}"
        )
    src = meta["source"]
    if not isinstance(src, dict):
        raise IngestionError("metadata.source must be a mapping")
    if "provenance" not in src:
        raise IngestionError("metadata.source must declare 'provenance'")
    if src["provenance"] not in ALLOWED_INGEST_PROVENANCE:
        raise IngestionError(
            f"ingest requires provenance of 'sourced' or 'verified'; got "
            f"{src['provenance']!r}. Placeholder tables are authored by hand."
        )


# -- CSV validation ---------------------------------------------------------


def _read_and_validate_csv(path: Path, table: str) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise IngestionError(f"cannot read CSV file {path}: {exc}") from exc
    reader = csv.DictReader(text.splitlines())
    required = _TABLE_SCHEMAS[table]
    fields = reader.fieldnames or []
    missing = [c for c in required if c not in fields]
    if missing:
        raise IngestionError(
            f"CSV missing required columns for table {table!r}: {missing}"
        )
    rows = [{k: (v or "").strip() for k, v in row.items()} for row in reader]
    if not rows:
        raise IngestionError("CSV has no data rows")

    validator = _row_validator_for(table)
    for i, row in enumerate(rows, start=2):
        for col in required:
            if not row.get(col):
                raise IngestionError(f"CSV line {i}: missing required value for {col}")
        validator(row, i)

    # Emit a canonical CSV (just the required columns, preserving row order).
    buf = StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(required), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: row[k] for k in required})
    return buf.getvalue()


def _row_validator_for(table: str):
    if table == "age_sex":
        return _validate_age_sex_row
    return _validate_category_row


def _validate_age_sex_row(row: dict[str, str], line: int) -> None:
    try:
        lo = int(row["age_low"])
        hi = int(row["age_high"])
    except ValueError as exc:
        raise IngestionError(
            f"CSV line {line}: age_low and age_high must be integers"
        ) from exc
    if lo < 0 or hi < lo:
        raise IngestionError(
            f"CSV line {line}: invalid age range age_low={lo}, age_high={hi}"
        )
    if row["sex"] not in SEX_STRATA:
        raise IngestionError(
            f"CSV line {line}: sex must be one of {list(SEX_STRATA)}; got {row['sex']!r}"
        )
    _validate_weight(row["weight"], line)


def _validate_category_row(row: dict[str, str], line: int) -> None:
    _validate_weight(row["weight"], line)


def _validate_weight(raw: str, line: int) -> None:
    try:
        w = float(raw)
    except ValueError as exc:
        raise IngestionError(
            f"CSV line {line}: weight must be a number; got {raw!r}"
        ) from exc
    if w <= 0:
        raise IngestionError(
            f"CSV line {line}: weight must be positive; got {w}"
        )


# -- Provenance sidecar -----------------------------------------------------


def _build_provenance(meta: dict[str, Any]) -> str:
    src = meta["source"]
    out: dict[str, Any] = {
        "table": meta["table"],
        "version": str(meta.get("version", "0.1.0")),
        "source": {
            "name": str(src.get("name", "")),
            "provenance": src["provenance"],
        },
    }
    for key in ("url", "note"):
        if src.get(key):
            out["source"][key] = str(src[key])
    if src.get("citations"):
        out["source"]["citations"] = src["citations"]
    return yaml.dump(
        out,
        Dumper=_NoAliasDumper,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
        width=100,
    )

"""Versioned Parquet export schema for Apex Atlas cohorts."""

from __future__ import annotations

PARQUET_SCHEMA_VERSION = "1.0.0"

PARQUET_SCHEMA_SPEC: dict[str, object] = {
    "schema_version": PARQUET_SCHEMA_VERSION,
    "description": (
        "One row per FHIR resource. `raw_json` holds the full resource; "
        "`id` and `subject_reference` are denormalized for analytics joins."
    ),
    "columns": [
        {"name": "id", "type": "string", "nullable": True, "description": "FHIR resource.id"},
        {
            "name": "subject_reference",
            "type": "string",
            "nullable": True,
            "description": "Patient subject reference when present",
        },
        {
            "name": "raw_json",
            "type": "string",
            "nullable": False,
            "description": "Full FHIR resource JSON",
        },
    ],
    "files": "One `{ResourceType}.parquet` per resource type in the output directory.",
}

# Parquet export schema

*Version 1.0.0 — see also `parquet-schema.json` written beside each Parquet cohort.*

## Layout

Each `atlas generate --format parquet` run produces:

- `{ResourceType}.parquet` — one file per FHIR resource type emitted
- `parquet-schema.json` — machine-readable column spec
- `generation-metadata.json` — cohort manifest (`parquet_schema_version` field)

## Columns (v1.0.0)

| Column | Type | Description |
| --- | --- | --- |
| `id` | string | FHIR `resource.id` |
| `subject_reference` | string | Patient subject reference when present |
| `raw_json` | string | Full resource JSON (parse with `json.loads`) |

## Example (pandas)

```python
import json
import pandas as pd

df = pd.read_parquet("Patient.parquet")
patients = df["raw_json"].map(json.loads)
```

## Versioning

Breaking column changes bump `PARQUET_SCHEMA_VERSION` in `parker_atlas.export.parquet_schema` and are recorded in cohort metadata.

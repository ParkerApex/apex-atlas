"""
Ingestion pipelines for external data sources.

Each ingest module consumes a clean CSV (+ small metadata YAML) and
produces an artifact that Parker Atlas's runtime loaders accept. The
CSV format is the integration point — users responsible for extracting
public data (NHANES, ACS, BRFSS, etc.) transform it into Atlas's CSV
shape, then run the appropriate `atlas ingest` command.

Why CSV as the integration point:
- Every data source has its own native format (XPT, SAS, PUMS CSV, API).
  Rather than bundling parsers for each, Atlas accepts a simple tabular
  CSV that the user prepares with whatever tooling they prefer.
- Provenance metadata lives in a separate YAML so citations and
  tolerance policy are authored once, independent of the numbers.
- The ingest path re-validates its own output through the runtime
  loader, so bad metadata fails at ingest time rather than at generate
  time.
"""

from parker_atlas.ingest.demographics import ingest_demographics
from parker_atlas.ingest.prevalence import IngestionError, ingest_prevalence

__all__ = ["IngestionError", "ingest_prevalence", "ingest_demographics"]

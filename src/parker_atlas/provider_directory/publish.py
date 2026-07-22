"""Serialize a Plan-Net provider directory to a bulk NDJSON export + manifest.

Mirrors the FHIR Bulk Data / SMART Scheduling Links convention: a JSON manifest
whose ``output`` array links one NDJSON file per resource type.
"""

from __future__ import annotations

import json
from pathlib import Path

from parker_atlas.provider_directory.directory import ProviderDirectory

# Manifest order follows the Plan-Net resource graph (networks/orgs first).
MANIFEST_TYPES = (
    "Organization",
    "Location",
    "Practitioner",
    "PractitionerRole",
    "HealthcareService",
    "InsurancePlan",
    "Endpoint",
)


def _rows(directory: ProviderDirectory) -> dict[str, list[dict]]:
    return {
        "Organization": directory.organizations,
        "Location": directory.locations,
        "Practitioner": directory.practitioners,
        "PractitionerRole": directory.practitioner_roles,
        "HealthcareService": directory.healthcare_services,
        "InsurancePlan": directory.insurance_plans,
        "Endpoint": directory.endpoints,
    }


def build_manifest(
    directory: ProviderDirectory, *, base_url: str, transaction_time: str
) -> dict:
    base = base_url.rstrip("/")
    rows = _rows(directory)
    return {
        "transactionTime": transaction_time,
        "request": f"{base}/$bulk-publish",
        "output": [
            {"type": t, "url": f"{base}/{t}.ndjson"} for t in MANIFEST_TYPES if rows[t]
        ],
        "error": [],
    }


def write_bulk_publish(
    directory: ProviderDirectory, out_dir: Path, *, base_url: str, transaction_time: str
) -> Path:
    """Write the manifest + one NDJSON file per resource type. Returns the manifest path."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for rtype, rows in _rows(directory).items():
        with (out_dir / f"{rtype}.ndjson").open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row) + "\n")
    manifest = build_manifest(
        directory, base_url=base_url, transaction_time=transaction_time
    )
    manifest_json = json.dumps(manifest, indent=2) + "\n"
    manifest_path = out_dir / "bulk-publish-manifest.json"
    manifest_path.write_text(manifest_json, encoding="utf-8")
    # Also publish at the literal `$bulk-publish` path the manifest advertises in
    # its `request` field, so the entry-point URL resolves on static hosting
    # (GitHub raw), not only on the live `atlas serve` API.
    (out_dir / "$bulk-publish").write_text(manifest_json, encoding="utf-8")
    return manifest_path

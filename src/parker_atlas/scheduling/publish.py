"""
Serialize a SMART Scheduling Links dataset to the ``$bulk-publish`` payload.

The bulk-publish payload is a JSON manifest whose ``output`` array links one
NDJSON file per resource type (Location, Schedule, Slot). This module builds
that manifest and writes the NDJSON files, following the SMART Scheduling Links
specification (https://github.com/smart-on-fhir/smart-scheduling-links).
"""

from __future__ import annotations

import json
from pathlib import Path

from parker_atlas.scheduling.links import SchedulingDataset

# Resource types published in the manifest, in spec order. Appointment is
# written alongside for convenience but is NOT advertised in the manifest
# (SMART Scheduling Links publishes availability, not bookings).
MANIFEST_TYPES = ("Location", "Schedule", "Slot")


def build_manifest(
    dataset: SchedulingDataset,
    *,
    base_url: str,
    transaction_time: str,
) -> dict:
    """Build the ``$bulk-publish`` manifest for ``dataset``.

    ``base_url`` is the directory the NDJSON files are published under; each
    ``output`` entry is ``{base_url}/{Type}.ndjson``.
    """
    base = base_url.rstrip("/")
    present = {
        "Location": dataset.locations,
        "Schedule": dataset.schedules,
        "Slot": dataset.slots,
    }
    return {
        "transactionTime": transaction_time,
        "request": f"{base}/$bulk-publish",
        "output": [
            {"type": t, "url": f"{base}/{t}.ndjson"}
            for t in MANIFEST_TYPES
            if present[t]
        ],
        "error": [],
    }


def _write_ndjson(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")


def write_bulk_publish(
    dataset: SchedulingDataset,
    out_dir: Path,
    *,
    base_url: str,
    transaction_time: str,
    include_appointments: bool = True,
) -> Path:
    """Write the manifest + NDJSON files to ``out_dir``.

    Returns the path of the written ``bulk-publish-manifest.json``.
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    _write_ndjson(out_dir / "Location.ndjson", dataset.locations)
    _write_ndjson(out_dir / "Schedule.ndjson", dataset.schedules)
    _write_ndjson(out_dir / "Slot.ndjson", dataset.slots)
    if include_appointments and dataset.appointments:
        _write_ndjson(out_dir / "Appointment.ndjson", dataset.appointments)

    manifest = build_manifest(
        dataset, base_url=base_url, transaction_time=transaction_time
    )
    manifest_json = json.dumps(manifest, indent=2) + "\n"
    manifest_path = out_dir / "bulk-publish-manifest.json"
    manifest_path.write_text(manifest_json, encoding="utf-8")
    # Also publish the manifest at the literal `$bulk-publish` path the manifest's
    # own `request` field (and the SMART Scheduling Links convention) advertises,
    # so the entry-point URL resolves on static hosting (e.g. GitHub raw), not
    # only on the live `atlas serve` API where `$bulk-publish` is an endpoint.
    (out_dir / "$bulk-publish").write_text(manifest_json, encoding="utf-8")
    return manifest_path

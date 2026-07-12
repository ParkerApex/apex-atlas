"""Build the CMS Connectathon 2026 SMART Scheduling Links bulk-publish dataset.

Thin wrapper over the general ``parker_atlas.scheduling`` feature
(also exposed as ``atlas publish-scheduling``). It pins the connectathon
parameters and points the manifest at the raw files as published on the
connectathon branch. Regenerate with:

    python scripts/build_cms_connectathon_scheduling.py

Everything is synthetic and deterministic. Patient references for the booked
Appointments are read from the companion Patient bulk export so they resolve
against the same cohort.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from parker_atlas.scheduling import (
    SchedulingConfig,
    generate_scheduling_dataset,
    write_bulk_publish,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "samples" / "cms-connectathon-2026" / "scheduling"
PATIENT_NDJSON = (
    REPO_ROOT / "samples" / "cms-connectathon-2026" / "patients" / "Patient.ndjson"
)

# The manifest advertises the raw files as committed on the connectathon branch.
PUBLISH_BASE = (
    "https://raw.githubusercontent.com/ParkerApex/apex-atlas/"
    "cms-connectathon-2026/samples/cms-connectathon-2026/scheduling"
)
# Fixed transaction time keeps re-runs byte-stable (no wall-clock in output).
TRANSACTION_TIME = "2026-07-12T00:00:00Z"


def load_patient_ids() -> list[str]:
    ids: list[str] = []
    with PATIENT_NDJSON.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                ids.append(json.loads(line)["id"])
    return ids


def main() -> None:
    config = SchedulingConfig(
        sites=40,
        service_keys=("general-practice", "immunization"),
        window_start=date(2026, 7, 13),
        weeks=4,
        day_start_hour=8,
        day_end_hour=17,
        slot_minutes=60,
        booked_fraction=0.20,
        seed=20260712,
        booking_base_url="https://booking.example.org",
    )
    dataset = generate_scheduling_dataset(
        config, patient_ids=load_patient_ids(), created=TRANSACTION_TIME
    )
    write_bulk_publish(
        dataset,
        OUT_DIR,
        base_url=PUBLISH_BASE,
        transaction_time=TRANSACTION_TIME,
    )
    print(" ".join(f"{k}={v}" for k, v in dataset.counts.items()))


if __name__ == "__main__":
    main()

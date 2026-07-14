#!/usr/bin/env python3
"""
Scale the clinician roster (`practitioners.csv`) to a realistic size for the
20,000-patient connectathon population.

The first rows of `practitioners.csv` are hand-curated, named anchors (kept
verbatim, including the test-pinned first row). This script preserves those and
*appends* deterministically-generated clinicians until the roster reaches
``TARGET`` rows, distributing the additions across specialties with a
primary-care-heavy weighting — the shape of a medical group that serves a panel
of ~20k patients at roughly one clinician per ~130 patients.

The generation primitives (specialty catalog, name pools, NPPES-valid NPI
sequence, largest-remainder apportionment) live in
:mod:`parker_atlas.provider_directory.roster` so this build-time script and the
on-demand directory generator stay in lock-step. Every generated NPI is a valid
10-digit individual NPI. Deterministic: same TARGET + same anchors → byte-
identical output.

Usage:
    python scripts/expand_provider_roster.py            # write to TARGET (150)
    python scripts/expand_provider_roster.py --target 200
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from parker_atlas.provider_directory.roster import DEFAULT_SEED, generate_additional
from parker_atlas.references import PractitionerRow

CSV_PATH = (
    Path(__file__).resolve().parent.parent
    / "src/parker_atlas/references/tables/practitioners.csv"
)

TARGET = 150

FIELDS = [
    "npi", "family", "given", "prefix",
    "taxonomy_code", "taxonomy_display", "encounter_class", "facility_npi",
]


def _row_dict(r: PractitionerRow) -> dict[str, str]:
    return {
        "npi": r.npi, "family": r.family, "given": r.given, "prefix": r.prefix,
        "taxonomy_code": r.taxonomy_code, "taxonomy_display": r.taxonomy_display,
        "encounter_class": r.encounter_class, "facility_npi": r.facility_npi,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=TARGET)
    args = ap.parse_args()

    with CSV_PATH.open(encoding="utf-8") as f:
        anchors = list(csv.DictReader(f))

    anchor_rows = tuple(
        PractitionerRow(
            npi=r["npi"], family=r["family"], given=r["given"], prefix=r["prefix"],
            taxonomy_code=r["taxonomy_code"], taxonomy_display=r["taxonomy_display"],
            encounter_class=r["encounter_class"], facility_npi=r["facility_npi"],
        )
        for r in anchors
    )
    n_add = max(0, args.target - len(anchor_rows))
    generated = generate_additional(anchor_rows, n_add, DEFAULT_SEED)

    rows = anchors + [_row_dict(r) for r in generated]
    with CSV_PATH.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)

    print(f"wrote {CSV_PATH} — {len(rows)} clinicians "
          f"({len(anchors)} anchors + {len(generated)} generated)")


if __name__ == "__main__":
    main()

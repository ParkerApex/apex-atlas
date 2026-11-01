"""Find synthetic NPIs that are not assigned in the national NPPES registry.

Atlas clinicians must never carry a real person's NPI. NPPES has no reserved
test range, so candidates are generated (valid Luhn check digit over the
'80840' prefix) and each is looked up against the public CMS NPPES NPI
Registry API; only numbers with zero results are kept.

    python scripts/verify_npis_nppes.py --start 199876000 --count 45 \
        --out src/parker_atlas/references/tables/scheduling_npis.csv

Re-run to re-verify a pinned list: --verify path/to/scheduling_npis.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import time
import urllib.request
from datetime import date
from pathlib import Path

from parker_atlas.provider_directory.roster import full_npi

API = "https://npiregistry.cms.hhs.gov/api/?version=2.1&number={npi}"


def nppes_count(npi: str) -> int:
    with urllib.request.urlopen(API.format(npi=npi), timeout=20) as resp:
        return int(json.load(resp).get("result_count", 0))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, help="first 9-digit base to try")
    ap.add_argument("--count", type=int, default=45)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--verify", type=Path, help="re-check an existing CSV")
    args = ap.parse_args()

    if args.verify:
        rows = list(csv.DictReader(args.verify.open()))
        bad = [r["npi"] for r in rows if nppes_count(r["npi"]) > 0]
        print(f"checked {len(rows)}; assigned in NPPES: {bad or 'none'}")
        raise SystemExit(1 if bad else 0)

    kept: list[str] = []
    base = args.start
    while len(kept) < args.count:
        npi = full_npi(str(base).zfill(9))
        base += 1
        n = nppes_count(npi)
        print(f"{npi} {'ASSIGNED - skipped' if n else 'unassigned'}")
        if not n:
            kept.append(npi)
        time.sleep(0.2)  # be polite to the public API
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["npi", "nppes_checked", "nppes_result_count"])
        for npi in kept:
            w.writerow([npi, date.today().isoformat(), 0])
    print(f"wrote {len(kept)} unassigned NPIs to {args.out}")


if __name__ == "__main__":
    main()

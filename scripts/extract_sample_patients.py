"""Extract a few full, human-readable patient records from the CMS Connectathon
2026 NDJSON bulk export.

The bulk `$export` files hold one resource per line across many files, which is
awkward to read by hand. This script reassembles a small, varied selection of
real patients from that export into pretty-printed FHIR **transaction Bundles**
(one JSON file per patient) — byte-for-byte what `atlas generate --format
fhir-r4` would have produced for those patients — so reviewers can open a single
readable file per patient.

Selection favors variety: several patients with distinct condition profiles plus
one minimal (healthy) record. Output goes to
``samples/cms-connectathon-2026/patients/examples/``.

Run:

    python scripts/extract_sample_patients.py
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from parker_atlas.fhir.bundle import build_bundle, fullurl_for_gpx, fullurl_for_resource
from parker_atlas.gpx import GPX

REPO_ROOT = Path(__file__).resolve().parent.parent
PATIENTS_DIR = REPO_ROOT / "samples" / "cms-connectathon-2026" / "patients"
OUT_DIR = PATIENTS_DIR / "examples"

# Files that carry per-patient resources (linked via subject/patient/beneficiary).
SHARED_TYPES = {"Organization", "InsurancePlan"}
PATIENT_REF_KEYS = ("subject", "patient", "beneficiary")
N_SAMPLES = 5


def patient_ref(resource: dict) -> str | None:
    for key in PATIENT_REF_KEYS:
        ref = resource.get(key)
        if isinstance(ref, dict) and isinstance(ref.get("reference"), str):
            return ref["reference"]
    return None


def condition_signature(resource: dict) -> str:
    code = resource.get("code", {})
    if code.get("text"):
        return code["text"]
    for coding in code.get("coding", []):
        if coding.get("display"):
            return coding["display"]
    return "unknown"


def load_ndjson(path: Path):
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def main() -> None:
    # Map patient GPX id -> Patient resource, and fullUrl -> GPX id.
    patients: dict[str, dict] = {}
    fullurl_to_gpx: dict[str, str] = {}
    for res in load_ndjson(PATIENTS_DIR / "Patient.ndjson"):
        gpx_id = res["id"]
        patients[gpx_id] = res
        fullurl_to_gpx[str(fullurl_for_gpx(GPX.parse(gpx_id)))] = gpx_id

    shared: dict[str, list[dict]] = {t: [] for t in SHARED_TYPES}
    for t in SHARED_TYPES:
        p = PATIENTS_DIR / f"{t}.ndjson"
        if p.exists():
            shared[t] = list(load_ndjson(p))

    clinical_files = sorted(
        p
        for p in PATIENTS_DIR.glob("*.ndjson")
        if p.stem not in SHARED_TYPES and p.stem != "Patient"
    )

    # Pass 1 — lightweight profile per patient: resource counts + condition set.
    counts: dict[str, int] = defaultdict(int)
    conditions: dict[str, set[str]] = defaultdict(set)
    for f in clinical_files:
        is_condition = f.stem == "Condition"
        for res in load_ndjson(f):
            ref = patient_ref(res)
            gpx_id = fullurl_to_gpx.get(ref) if ref else None
            if gpx_id is None:
                continue
            counts[gpx_id] += 1
            if is_condition:
                conditions[gpx_id].add(condition_signature(res))

    # Selection — pick for contrast: one multi-condition (richest), one with a
    # few conditions, one single-condition, plus a healthy Patient+Coverage
    # record. Ties broken by richest record, so each sample is well-populated.
    def richest(pred) -> str | None:
        pool = [g for g in patients if pred(g)]
        return max(pool, key=lambda g: counts.get(g, 0), default=None)

    ncond = lambda g: len(conditions.get(g, set()))  # noqa: E731
    chosen: list[str] = []
    for pick in (
        richest(lambda g: ncond(g) >= 4),            # multi-condition, richest
        richest(lambda g: ncond(g) in (2, 3)),       # a few conditions
        richest(lambda g: ncond(g) == 1),            # single condition
        richest(lambda g: ncond(g) == 0 and counts.get(g, 0) >= 1),  # healthy + coverage
    ):
        if pick is not None and pick not in chosen:
            chosen.append(pick)
    # Backfill with distinct-signature records if any bucket was empty.
    if len(chosen) < N_SAMPLES:
        seen = {frozenset(conditions.get(g, set())) for g in chosen}
        for gpx_id in sorted(patients, key=lambda g: counts.get(g, 0), reverse=True):
            sig = frozenset(conditions.get(gpx_id, set()))
            if gpx_id not in chosen and sig not in seen:
                chosen.append(gpx_id)
                seen.add(sig)
            if len(chosen) == N_SAMPLES:
                break
    # Present richest → simplest.
    chosen = sorted(chosen, key=lambda g: counts.get(g, 0), reverse=True)
    targets = set(chosen)

    # Pass 2 — collect every resource belonging to the chosen patients.
    buckets: dict[str, list[dict]] = {g: [] for g in targets}
    target_fullurls = {str(fullurl_for_gpx(GPX.parse(g))): g for g in targets}
    for f in clinical_files:
        for res in load_ndjson(f):
            ref = patient_ref(res)
            gpx_id = target_fullurls.get(ref) if ref else None
            if gpx_id is not None:
                buckets[gpx_id].append(res)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    index_rows: list[str] = []
    for gpx_id in chosen:
        gpx = GPX.parse(gpx_id)
        extras = list(buckets[gpx_id])

        # Pull in any shared Organization / InsurancePlan the patient's
        # resources reference, so each Bundle is self-contained.
        referenced = {
            v["reference"]
            for res in extras
            for v in _iter_references(res)
        }
        for t in SHARED_TYPES:
            for r in shared[t]:
                if str(fullurl_for_resource(gpx, r)) in referenced:
                    extras.append(r)

        bundle = build_bundle(gpx, patients[gpx_id], extras)
        (OUT_DIR / f"{gpx_id}.json").write_text(
            json.dumps(bundle, indent=2) + "\n", encoding="utf-8"
        )

        conds = sorted(conditions.get(gpx_id, set())) or ["(no active conditions)"]
        index_rows.append(
            f"| `{gpx_id}.json` | {len(bundle['entry'])} | {', '.join(conds)} |"
        )
        print(f"wrote {gpx_id}.json — {len(bundle['entry'])} entries")

    _write_readme(index_rows)


def _iter_references(resource: dict):
    """Yield every dict that has a string 'reference' anywhere in the resource."""
    stack = [resource]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            if isinstance(node.get("reference"), str):
                yield node
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)


def _write_readme(index_rows: list[str]) -> None:
    body = (
        "# Sample patient records\n\n"
        "Human-readable, pretty-printed FHIR R4 **transaction Bundles** for a few "
        "real patients drawn from the 20,000-patient bulk export in "
        "[`../`](../). Each file is a complete record for one patient — the "
        "`Patient` plus all of their linked resources (conditions, encounters, "
        "observations, medications, immunizations, coverage) — so you can read a "
        "whole patient in one file instead of scanning the large NDJSON.\n\n"
        "These are identical to what `atlas generate --format fhir-r4` emits for "
        "these patients; the full population lives in the `*.ndjson` files one "
        "directory up.\n\n"
        "| File | Entries | Conditions |\n| --- | ---: | --- |\n"
        + "\n".join(index_rows)
        + "\n\nRegenerate with `python scripts/extract_sample_patients.py`.\n"
    )
    (OUT_DIR / "README.md").write_text(body, encoding="utf-8")


if __name__ == "__main__":
    main()

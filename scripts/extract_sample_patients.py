"""Extract a few full, human-readable patient records from the CMS Connectathon
2026 NDJSON bulk export.

The bulk `$export` files hold one resource per line across many files, which is
awkward to read by hand. This script reassembles a small, varied selection of
real patients into pretty-printed FHIR **collection Bundles** (one JSON file per
patient) — the Patient plus all of their linked resources — so reviewers can
open a single readable file per patient.

The export uses relative references (`Patient/<id>`), so each Bundle keeps those
references and sets `fullUrl` to a stable base URL + `ResourceType/id`, leaving
every reference resolvable within the file.

Output goes to ``samples/cms-connectathon-2026/patients/examples/``.

Run:

    python scripts/extract_sample_patients.py
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PATIENTS_DIR = REPO_ROOT / "samples" / "cms-connectathon-2026" / "patients"
OUT_DIR = PATIENTS_DIR / "examples"

FHIR_BASE = "https://parkerapex.com/atlas/fhir"
SHARED_TYPES = {"Organization", "InsurancePlan"}
PATIENT_REF_KEYS = ("subject", "patient", "beneficiary")
N_SAMPLES = 5


def patient_ref_id(resource: dict) -> str | None:
    """Return the referenced patient id from subject/patient/beneficiary."""
    for key in PATIENT_REF_KEYS:
        ref = resource.get(key)
        if isinstance(ref, dict) and isinstance(ref.get("reference"), str):
            value = ref["reference"]
            if value.startswith("Patient/"):
                return value.split("/", 1)[1]
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


def _iter_references(resource: dict):
    stack = [resource]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            if isinstance(node.get("reference"), str):
                yield node["reference"]
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)


def main() -> None:
    patients: dict[str, dict] = {r["id"]: r for r in load_ndjson(PATIENTS_DIR / "Patient.ndjson")}

    shared: dict[str, dict] = {}  # "Type/id" -> resource
    for t in SHARED_TYPES:
        p = PATIENTS_DIR / f"{t}.ndjson"
        if p.exists():
            for r in load_ndjson(p):
                shared[f"{t}/{r['id']}"] = r

    clinical_files = sorted(
        p for p in PATIENTS_DIR.glob("*.ndjson")
        if p.stem not in SHARED_TYPES and p.stem != "Patient"
    )

    # Pass 1 — per-patient resource counts + condition signatures.
    counts: dict[str, int] = defaultdict(int)
    conditions: dict[str, set[str]] = defaultdict(set)
    for f in clinical_files:
        is_condition = f.stem == "Condition"
        for res in load_ndjson(f):
            gpx_id = patient_ref_id(res)
            if gpx_id is None or gpx_id not in patients:
                continue
            counts[gpx_id] += 1
            if is_condition:
                conditions[gpx_id].add(condition_signature(res))

    # Selection — one multi-condition (richest), a few, single, and a healthy record.
    def richest(pred) -> str | None:
        pool = [g for g in patients if pred(g)]
        return max(pool, key=lambda g: counts.get(g, 0), default=None)

    ncond = lambda g: len(conditions.get(g, set()))  # noqa: E731
    chosen: list[str] = []
    for pick in (
        richest(lambda g: ncond(g) >= 4),
        richest(lambda g: ncond(g) in (2, 3)),
        richest(lambda g: ncond(g) == 1),
        richest(lambda g: ncond(g) == 0 and counts.get(g, 0) >= 1),
    ):
        if pick is not None and pick not in chosen:
            chosen.append(pick)
    if len(chosen) < N_SAMPLES:
        seen = {frozenset(conditions.get(g, set())) for g in chosen}
        for gpx_id in sorted(patients, key=lambda g: counts.get(g, 0), reverse=True):
            sig = frozenset(conditions.get(gpx_id, set()))
            if gpx_id not in chosen and sig not in seen:
                chosen.append(gpx_id)
                seen.add(sig)
            if len(chosen) == N_SAMPLES:
                break

    chosen = sorted(chosen, key=lambda g: counts.get(g, 0), reverse=True)
    targets = set(chosen)

    # Pass 2 — collect every resource belonging to the chosen patients.
    buckets: dict[str, list[dict]] = {g: [] for g in targets}
    for f in clinical_files:
        for res in load_ndjson(f):
            gpx_id = patient_ref_id(res)
            if gpx_id in targets:
                buckets[gpx_id].append(res)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    index_rows: list[str] = []
    for gpx_id in chosen:
        entries = [patients[gpx_id], *buckets[gpx_id]]
        # Pull in any shared Organization / InsurancePlan the resources reference.
        referenced = {r for res in entries for r in _iter_references(res)}
        for key in referenced:
            if key in shared:
                entries.append(shared[key])

        bundle = {
            "resourceType": "Bundle",
            "type": "collection",
            "entry": [
                {"fullUrl": f"{FHIR_BASE}/{r['resourceType']}/{r['id']}", "resource": r}
                for r in entries
            ],
        }
        (OUT_DIR / f"{gpx_id}.json").write_text(
            json.dumps(bundle, indent=2) + "\n", encoding="utf-8"
        )
        conds = sorted(conditions.get(gpx_id, set())) or ["(no active conditions)"]
        index_rows.append(f"| `{gpx_id}.json` | {len(entries)} | {', '.join(conds)} |")
        print(f"wrote {gpx_id}.json — {len(entries)} entries")

    _write_readme(index_rows)


def _write_readme(index_rows: list[str]) -> None:
    body = (
        "# Sample patient records\n\n"
        "Human-readable, pretty-printed FHIR R4 **collection Bundles** for a few "
        "real patients drawn from the 20,000-patient bulk export in "
        "[`../`](../). Each file is a complete record for one patient — the "
        "`Patient` plus all of their linked resources (conditions, encounters, "
        "observations, medications, immunizations, coverage) — so you can read a "
        "whole patient in one file instead of scanning the large NDJSON.\n\n"
        "References are relative (`Patient/<id>`, …) and resolve within each "
        "Bundle; the full population lives in the `*.ndjson` files one directory "
        "up.\n\n"
        "| File | Entries | Conditions |\n| --- | ---: | --- |\n"
        + "\n".join(index_rows)
        + "\n\nRegenerate with `python scripts/extract_sample_patients.py`.\n"
    )
    (OUT_DIR / "README.md").write_text(body, encoding="utf-8")


if __name__ == "__main__":
    main()

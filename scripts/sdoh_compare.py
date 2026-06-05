#!/usr/bin/env python3
"""SDoH causal-signal comparison harness — Atlas vs. any other FHIR generator.

The SDoH causal benchmark (scripts/sdoh_causal_benchmark.py) measures, within an
Atlas cohort, how utilization falls as social-risk burden rises. This harness
generalizes that measurement so it runs against *any* FHIR cohort — an Atlas
cohort and, say, a Synthea export — and prints them side by side.

The hypothesis under test: a generator that models SDoH *causally* (Atlas)
shows utilization declining with SDoH burden — a steep negative "causal slope".
A generator that attaches SDoH as a non-causal tag/attribute shows a roughly
**flat** slope: same utilization regardless of burden.

It ingests either a directory of FHIR Bundles (`*.json`, one per patient — the
shape both Atlas and Synthea emit) or a directory of `$export` NDJSON
(`*.ndjson`, one file per resource type, linked by `subject`/`patient`).

SDoH-positive screens are detected from configurable (question-code,
positive-answer-code) pairs. The default set is Atlas's Gravity SDOHCC codes;
pass `--screens screens.json` to supply another generator's codes (e.g. the
LOINC codes a given Synthea version emits) so the comparison is apples-to-apples.

Usage
-----
    # Atlas vs Synthea, side by side
    python scripts/sdoh_compare.py \
        --cohort atlas=./atlas_out \
        --cohort synthea=/path/to/synthea/output/fhir \
        [--screens synthea_screens.json] [--out docs/sdoh-vs-synthea.md]

    # Single cohort (just measure one)
    python scripts/sdoh_compare.py --cohort atlas=./atlas_out
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

# Default: Atlas Gravity SDOHCC (question LOINC, positive-answer LOINC) per domain.
DEFAULT_SCREENS = {
    "food_insecurity": ["88122-0", "LA33-6"],
    "housing_instability": ["71802-3", "LA31996-4"],
    "transportation_barrier": ["93030-5", "LA33-6"],
    "financial_strain": ["96780-2", "LA33-6"],
    "inadequate_social_support": ["54899-0", "LA6270-8"],
}


def _codes(concept: dict) -> set[str]:
    return {c.get("code") for c in (concept or {}).get("coding", []) if c.get("code")}


def _iter_patient_resource_sets(path: Path):
    """Yield, per patient, the list of that patient's resource dicts.

    Supports a dir of per-patient FHIR Bundles (*.json with entry[]) or a dir of
    NDJSON ($export) files grouped by Patient reference.
    """
    ndjson = sorted(path.glob("*.ndjson"))
    if ndjson:
        by_patient: dict[str, list[dict]] = collections.defaultdict(list)
        patients: list[str] = []
        for f in ndjson:
            for line in f.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                r = json.loads(line)
                if r.get("resourceType") == "Patient":
                    pid = f"Patient/{r.get('id')}"
                    patients.append(pid)
                    by_patient[pid].append(r)
                else:
                    ref = (r.get("subject") or r.get("patient") or {}).get("reference", "")
                    # tolerate "Patient/x" and "urn:uuid:x"
                    key = ref.split("urn:uuid:")[-1]
                    by_patient.setdefault(ref, []).append(r)
                    by_patient.setdefault(f"Patient/{key}", []).append(r)
        for pid in patients:
            yield by_patient.get(pid, [])
        return
    for f in sorted(path.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if data.get("resourceType") == "Bundle":
            yield [e["resource"] for e in data.get("entry", []) if "resource" in e]


def _positive_screen_count(resources: list[dict], screens: dict) -> int:
    pairs = [(q, a) for q, a in screens.values()]
    n = 0
    for r in resources:
        if r.get("resourceType") != "Observation":
            continue
        qcodes = _codes(r.get("code"))
        acodes = _codes(r.get("valueCodeableConcept"))
        for q, a in pairs:
            if q in qcodes and a in acodes:
                n += 1
    return n


def _amb_encounters(resources: list[dict]) -> int:
    n = 0
    for r in resources:
        if r.get("resourceType") != "Encounter":
            continue
        cls = r.get("class") or {}
        # FHIR R4 Encounter.class is a Coding; some exports use a list/CodeableConcept.
        code = None
        if isinstance(cls, dict):
            code = cls.get("code") or _first_coding_code(cls)
        elif isinstance(cls, list):
            code = _first_coding_code(cls[0]) if cls else None
        if code == "AMB":
            n += 1
    return n


def _first_coding_code(obj) -> str | None:
    if isinstance(obj, dict):
        for c in obj.get("coding", []) or []:
            if c.get("code"):
                return c["code"]
    return None


def _med_requests(resources: list[dict]) -> int:
    return sum(1 for r in resources if r.get("resourceType") == "MedicationRequest")


def measure_cohort(path: Path, screens: dict) -> dict:
    buckets: dict[int, list[tuple[int, int]]] = collections.defaultdict(list)
    total = 0
    any_screen = 0
    for resources in _iter_patient_resource_sets(path):
        total += 1
        burden = _positive_screen_count(resources, screens)
        if burden:
            any_screen += 1
        buckets[min(burden, 3)].append((_amb_encounters(resources), _med_requests(resources)))
    return {"total": total, "any_screen": any_screen, "buckets": buckets}


def _mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def _cohort_rows(buckets):
    rows = []
    base_amb = base_med = None
    for b in sorted(buckets):
        pairs = buckets[b]
        amb, med = _mean([a for a, _ in pairs]), _mean([m for _, m in pairs])
        if b == 0:
            base_amb, base_med = amb, med
        rows.append((b, len(pairs), amb, med))
    # causal slope: relative drop in AMB encounters from burden 0 to max bucket
    slope = None
    if base_amb and len(rows) > 1:
        top_amb = rows[-1][2]
        slope = (top_amb / base_amb) - 1.0
    return rows, slope


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cohort", action="append", default=[], metavar="LABEL=PATH",
                    help="A labeled cohort directory (repeatable).")
    ap.add_argument("--screens", type=Path, help="JSON {domain:[question_code,positive_code]} overriding the default Atlas SDOHCC codes.")
    ap.add_argument("--out", type=Path, help="Write a Markdown comparison here (else stdout).")
    args = ap.parse_args()
    if not args.cohort:
        ap.error("at least one --cohort LABEL=PATH is required")

    screens = DEFAULT_SCREENS
    if args.screens:
        screens = json.loads(args.screens.read_text(encoding="utf-8"))

    results = {}
    for spec in args.cohort:
        if "=" not in spec:
            ap.error(f"--cohort must be LABEL=PATH, got {spec!r}")
        label, path = spec.split("=", 1)
        results[label] = measure_cohort(Path(path), screens)

    md = _render(results, screens)
    if args.out:
        args.out.write_text(md, encoding="utf-8")
        sys.stderr.write(f"Wrote {args.out}\n")
    print(md)
    return 0


def _render(results: dict, screens: dict) -> str:
    lines = [
        "# SDoH causal-signal comparison",
        "",
        "_Generated by `scripts/sdoh_compare.py`._",
        "",
        "Each cohort's patients are bucketed by number of positive SDoH screens; "
        "we report mean ambulatory encounters and medication requests per bucket, "
        "and a **causal slope** = relative change in ambulatory encounters from "
        "burden 0 to the highest bucket. A causal SDoH model produces a steep "
        "negative slope; a non-causal (tag-only) model produces a roughly flat one.",
        "",
        f"SDoH screens detected via {len(screens)} (question, positive-answer) code "
        f"pairs: {', '.join(screens)}.",
        "",
    ]
    for label, res in results.items():
        rows, slope = _cohort_rows(res["buckets"])
        pct = 100.0 * res["any_screen"] / res["total"] if res["total"] else 0.0
        lines += [
            f"## {label}",
            "",
            f"- Patients: {res['total']:,} · with ≥1 positive SDoH screen: "
            f"{res['any_screen']:,} ({pct:.0f}%)",
            f"- **Causal slope (ambulatory encounters, burden 0 → max): "
            f"{'%+.0f%%' % (slope * 100) if slope is not None else 'n/a'}**",
            "",
            "| Positive screens | Patients | Mean ambulatory enc. | Mean medication reqs |",
            "|---|---:|---:|---:|",
        ]
        labels = {0: "0 (none)", 1: "1", 2: "2", 3: "3+"}
        for b, n, amb, med in rows:
            lines.append(f"| {labels[b]} | {n} | {amb:.2f} | {med:.2f} |")
        if res["any_screen"] == 0:
            lines += ["", "_No SDoH screens detected — supply this generator's screen "
                      "codes via `--screens` so burden can be measured._"]
        lines.append("")
    lines += [
        "## How to run the Synthea side",
        "",
        "Synthea (Java) is not bundled here. Generate a Synthea FHIR R4 export, then:",
        "",
        "```bash",
        "python scripts/sdoh_compare.py \\",
        "  --cohort atlas=./atlas_out \\",
        "  --cohort synthea=/path/to/synthea/output/fhir \\",
        "  --screens synthea_screens.json   # the LOINC screen codes your Synthea version emits",
        "```",
        "",
        "Provide `synthea_screens.json` as `{\"domain\": [\"<question LOINC>\", "
        "\"<positive-answer code>\"]}` matching how that Synthea version records SDoH "
        "screening. Because Synthea does not model SDoH → utilization causality, the "
        "expected result is a near-flat causal slope — the contrast this harness exists "
        "to make explicit.",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())

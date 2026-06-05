#!/usr/bin/env python3
"""SDoH causal-signal benchmark.

Demonstrates the capability that most distinguishes Apex Atlas from tag-only
generators (e.g. Synthea): social determinants of health are modeled as
*causes* that change utilization, not metadata attached to a patient.

Atlas's `--with-sdoh` overlay reduces the emit probability of ambulatory
encounters (transportation barriers) and medication requests (cost/financial
barriers) as a function of each patient's SDoH burden. So in the generated
FHIR, patients with more positive SDoH screens should have measurably FEWER
ambulatory encounters and medication requests — a monotonic causal gradient.

This script generates a chronic-disease cohort with `--with-sdoh`, classifies
each patient by number of positive SDoH screens, and reports mean ambulatory
encounters and medication requests per patient by burden level. A tag-only
generator would show a flat gradient (no causal effect); Atlas shows a decline.

Usage:
    PYTHONPATH=src python scripts/sdoh_causal_benchmark.py [--patients N] [--seed S]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# (question LOINC, positive-answer LOINC) per SDoH domain, from
# fhir/sdoh_observation.py. A patient screens positive for a domain when an
# Observation carries the question code AND the positive answer.
POSITIVE_SCREENS = {
    "food_insecurity": ("88122-0", "LA33-6"),
    "housing_instability": ("71802-3", "LA31996-4"),
    "transportation_barrier": ("93030-5", "LA33-6"),
    "financial_strain": ("96780-2", "LA33-6"),
    "inadequate_social_support": ("54899-0", "LA6270-8"),
}
# Modules with regular ambulatory visits + chronic meds, so there is utilization
# for barriers to suppress.
COHORT_MODULES = "hypertension,diabetes,hypercholesterolemia,depression,copd"


def _codes(concept: dict) -> set[str]:
    return {c.get("code") for c in (concept or {}).get("coding", []) if c.get("code")}


def _positive_screen_count(resources: list[dict]) -> int:
    n = 0
    for r in resources:
        if r.get("resourceType") != "Observation":
            continue
        qcodes = _codes(r.get("code"))
        acodes = _codes(r.get("valueCodeableConcept"))
        for q, a in POSITIVE_SCREENS.values():
            if q in qcodes and a in acodes:
                n += 1
    return n


def _amb_encounters(resources: list[dict]) -> int:
    n = 0
    for r in resources:
        if r.get("resourceType") != "Encounter":
            continue
        cls = r.get("class") or {}
        code = cls.get("code") if isinstance(cls, dict) else None
        if code == "AMB":
            n += 1
    return n


def _med_requests(resources: list[dict]) -> int:
    return sum(1 for r in resources if r.get("resourceType") == "MedicationRequest")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--patients", type=int, default=8000)
    ap.add_argument("--seed", type=int, default=20260604)
    ap.add_argument("--out", type=Path, default=REPO / "docs" / "sdoh-causal-benchmark.md")
    args = ap.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        cohort = Path(tmp) / "cohort"
        cmd = [
            sys.executable, "-m", "parker_atlas.cli", "generate",
            "--module", COHORT_MODULES, "--patients", str(args.patients),
            "--seed", str(args.seed), "--with-sdoh", "--out", str(cohort),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            sys.stderr.write(res.stderr[-1000:])
            return 1

        # burden -> [list of (amb, meds)]
        buckets: dict[int, list[tuple[int, int]]] = {}
        for f in cohort.glob("GPX-SYN-*.json"):
            bundle = json.loads(f.read_text(encoding="utf-8"))
            resources = [e["resource"] for e in bundle.get("entry", []) if "resource" in e]
            burden = _positive_screen_count(resources)
            buckets.setdefault(min(burden, 3), []).append(
                (_amb_encounters(resources), _med_requests(resources))
            )

    md = _render(buckets, args)
    args.out.write_text(md, encoding="utf-8")
    sys.stderr.write(f"\nWrote {args.out}\n")
    print(md)
    return 0


def _render(buckets: dict[int, list[tuple[int, int]]], args) -> str:
    def mean(xs):
        return sum(xs) / len(xs) if xs else 0.0

    labels = {0: "0 (none)", 1: "1", 2: "2", 3: "3+"}
    rows = []
    base_amb = base_med = None
    for b in sorted(buckets):
        pairs = buckets[b]
        amb = mean([a for a, _ in pairs])
        med = mean([m for _, m in pairs])
        if b == 0:
            base_amb, base_med = amb, med
        amb_rel = f"{(amb / base_amb - 1) * 100:+.0f}%" if base_amb else "—"
        med_rel = f"{(med / base_med - 1) * 100:+.0f}%" if base_med else "—"
        rows.append((labels[b], len(pairs), amb, amb_rel, med, med_rel))

    lines = [
        "# Apex Atlas — SDoH Causal-Signal Benchmark",
        "",
        "_Auto-generated by `scripts/sdoh_causal_benchmark.py`. Do not edit by hand._",
        "",
        "**Claim under test:** in Atlas, social determinants of health are causal "
        "variables, not metadata. Patients with more positive SDoH screens should "
        "have measurably fewer ambulatory encounters (transportation barriers) and "
        "medication requests (cost barriers) in the generated FHIR.",
        "",
        f"Cohort: `{COHORT_MODULES}`, N={args.patients:,}, seed {args.seed}, "
        f"generated with `--with-sdoh`. Burden = number of positive SDoH screens "
        f"per patient (capped at 3+).",
        "",
        "## Utilization by SDoH burden",
        "",
        "| SDoH positive screens | Patients | Mean ambulatory encounters | vs none | Mean medication requests | vs none |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for label, n, amb, amb_rel, med, med_rel in rows:
        lines.append(f"| {label} | {n} | {amb:.2f} | {amb_rel} | {med:.2f} | {med_rel} |")
    lines += [
        "",
        "## Interpretation",
        "",
        "A monotonic decline in ambulatory encounters and medication requests as "
        "SDoH burden rises is the causal signal: the barriers changed *what "
        "resources were generated*, so a model trained on this data learns the "
        "relationship between social circumstance and utilization.",
        "",
        "A tag-only generator (SDoH attached as a demographic attribute that does "
        "not affect emission) would show a **flat** gradient here — same mean "
        "utilization regardless of burden — which is why models trained on such "
        "data cannot learn the access effect that clinicians and care managers "
        "actually observe.",
        "",
        "_Rates are sourced/calibrated to BRFSS care-avoidance and Urban Institute "
        "cost-related non-adherence figures; see `core/sdoh.py`._",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())

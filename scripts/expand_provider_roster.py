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

Every generated NPI is a valid 10-digit individual NPI (NPPES Luhn check digit
over the "80840" issuer prefix), continuing the sequence past the curated block.
Deterministic: same TARGET + same anchors → byte-identical output.

Usage:
    python scripts/expand_provider_roster.py            # write to TARGET (150)
    python scripts/expand_provider_roster.py --target 200
"""

from __future__ import annotations

import argparse
import csv
import random
from pathlib import Path

CSV_PATH = (
    Path(__file__).resolve().parent.parent
    / "src/parker_atlas/references/tables/practitioners.csv"
)

TARGET = 150
SEED = 20260713

FIELDS = [
    "npi",
    "family",
    "given",
    "prefix",
    "taxonomy_code",
    "taxonomy_display",
    "encounter_class",
    "facility_npi",
]

# Given / family name pools — larger than the patient names.csv pools so a
# 150-clinician roster reads as distinct people. Synthetic, license-clean.
GIVEN = [
    "Aaron", "Priya", "Marcus", "Wei", "Sofia", "Diego", "Amara", "Noah",
    "Leila", "Omar", "Hana", "Ethan", "Yuki", "Carlos", "Nadia", "Ivan",
    "Grace", "Tariq", "Elena", "Kofi", "Mira", "Sean", "Ingrid", "Rohan",
    "Beatriz", "Lars", "Aisha", "Felix", "Ling", "Mateus", "Zara", "Oscar",
    "Freya", "Nikolai", "Imani", "Andre", "Sana", "Viktor", "Lucia", "Kai",
    "Rania", "Pedro", "Anja", "Malik", "Chiara", "Tomas", "Nia", "Bjorn",
    "Farah", "Dmitri", "Elsa", "Hugo", "Meera", "Soren", "Ana", "Rafael",
    "Yara", "Emil", "Divya", "Luka",
]
FAMILY = [
    "Abbott", "Bianchi", "Cho", "Diaz", "Espinoza", "Farrell", "Gupta",
    "Haas", "Ibrahim", "Jansen", "Kovac", "Lindqvist", "Mahmoud", "Nakamura",
    "Ortega", "Pappas", "Quintero", "Reddy", "Saito", "Toledo", "Ustinov",
    "Vasquez", "Walsh", "Xu", "Yildiz", "Zheng", "Baptiste", "Castillo",
    "Duarte", "Egorov", "Ferreira", "Grigoryan", "Hoffman", "Ismail",
    "Johansen", "Krishnan", "Laurent", "Moreau", "Ndiaye", "Okonkwo",
    "Petersen", "Rahman", "Solberg", "Tremblay", "Ueda", "Voss", "Weiss",
    "Yoon", "Zamora", "Adebayo", "Beckett", "Contreras", "Dumont", "Falk",
    "Gallardo", "Halvorsen", "Iversen", "Jindal", "Karlsson", "Lozano",
]

# Specialty catalog: (taxonomy_code, display, encounter_class, [facility_npi...])
# The `weight` column drives how many *additional* clinicians land in each
# specialty (largest-remainder apportionment of TARGET - len(anchors)).
# Facilities listed per specialty are rotated for a realistic site spread.
PRIMARY = ["2000000036", "2000000044", "2000000051"]
CATALOG = [
    # (taxonomy, display, class, facilities, weight)
    ("207R00000X", "Internal Medicine", "AMB", PRIMARY, 22),
    ("207Q00000X", "Family Medicine", "AMB", ["2000000036", "2000000044"], 18),
    ("363L00000X", "Nurse Practitioner", "AMB",
     ["2000000036", "2000000044", "2000000069", "2000000051"], 15),
    ("208000000X", "Pediatrics", "AMB", ["2000000069"], 9),
    ("363A00000X", "Physician Assistant", "AMB",
     ["2000000036", "2000000044", "2000000085"], 9),
    ("207P00000X", "Emergency Medicine", "EMER", ["2000000010"], 6),
    ("208M00000X", "Hospitalist", "IMP", ["2000000010"], 6),
    ("207V00000X", "Obstetrics & Gynecology", "AMB", ["2000000069"], 5),
    ("2084P0800X", "Psychiatry", "AMB", ["2000000077"], 5),
    ("207RC0000X", "Cardiovascular Disease", "AMB", ["2000000028"], 4),
    ("2085R0202X", "Diagnostic Radiology", "AMB", ["2000000093"], 4),
    ("207L00000X", "Anesthesiology", "IMP", ["2000000010"], 4),
    ("2084N0400X", "Neurology", "AMB", ["2000000077"], 3),
    ("207N00000X", "Dermatology", "AMB", ["2000000051"], 3),
    ("207X00000X", "Orthopaedic Surgery", "IMP", ["2000000085"], 3),
    ("207RG0100X", "Gastroenterology", "AMB", ["2000000051"], 2),
    ("208600000X", "Surgery", "IMP", ["2000000085"], 2),
    ("207W00000X", "Ophthalmology", "AMB", ["2000000085"], 2),
    ("207RH0003X", "Hematology & Oncology", "AMB", ["2000000101"], 2),
    ("207RE0101X", "Endocrinology Diabetes & Metabolism", "AMB", ["2000000051"], 1),
    ("207RN0300X", "Nephrology", "AMB", ["2000000051"], 1),
    ("207RP1001X", "Pulmonary Disease", "AMB", ["2000000051"], 1),
    ("207RI0200X", "Infectious Disease", "AMB", ["2000000051"], 1),
    ("207RR0500X", "Rheumatology", "AMB", ["2000000051"], 1),
    ("208800000X", "Urology", "AMB", ["2000000085"], 1),
    ("207Y00000X", "Otolaryngology", "AMB", ["2000000085"], 1),
    ("208100000X", "Physical Medicine & Rehabilitation", "AMB", ["2000000051"], 1),
    ("207RC0200X", "Critical Care Medicine", "IMP", ["2000000010"], 1),
    ("207RG0300X", "Geriatric Medicine", "AMB", ["2000000036"], 1),
    ("2085R0001X", "Radiation Oncology", "AMB", ["2000000101"], 1),
    ("207RI0011X", "Interventional Cardiology", "AMB", ["2000000028"], 1),
]


def npi_check_digit(base9: str) -> str:
    """NPPES Luhn mod-10 check digit over the '80840' issuer prefix."""
    digits = "80840" + base9
    total = 0
    for i, ch in enumerate(reversed(digits)):
        n = int(ch)
        if i % 2 == 0:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return str((10 - (total % 10)) % 10)


def full_npi(base9: str) -> str:
    return base9 + npi_check_digit(base9)


def apportion(weights: list[int], n: int) -> list[int]:
    """Largest-remainder apportionment of n across the given integer weights."""
    total = sum(weights)
    quotas = [w * n / total for w in weights]
    counts = [int(q) for q in quotas]
    remainder = n - sum(counts)
    order = sorted(range(len(weights)), key=lambda i: quotas[i] - counts[i], reverse=True)
    for i in order[:remainder]:
        counts[i] += 1
    return counts


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=TARGET)
    args = ap.parse_args()

    with CSV_PATH.open(encoding="utf-8") as f:
        anchors = list(csv.DictReader(f))

    anchor_npis = {r["npi"] for r in anchors}
    max_base = max(int(r["npi"][:9]) for r in anchors)
    n_add = max(0, args.target - len(anchors))

    weights = [c[4] for c in CATALOG]
    counts = apportion(weights, n_add)

    rng = random.Random(SEED)
    generated: list[dict[str, str]] = []
    base = max_base
    used_names: set[tuple[str, str]] = {(r["given"], r["family"]) for r in anchors}
    for (tax, display, cls, facilities, _w), k in zip(CATALOG, counts):
        for j in range(k):
            # deterministic distinct name
            for _ in range(200):
                given = rng.choice(GIVEN)
                family = rng.choice(FAMILY)
                if (given, family) not in used_names:
                    break
            used_names.add((given, family))
            base += 1
            npi = full_npi(str(base).zfill(9))
            assert npi not in anchor_npis
            facility = facilities[j % len(facilities)]
            prefix = "" if tax in ("363L00000X", "363A00000X") else "Dr."
            generated.append({
                "npi": npi,
                "family": family,
                "given": given,
                "prefix": prefix,
                "taxonomy_code": tax,
                "taxonomy_display": display,
                "encounter_class": cls,
                "facility_npi": facility,
            })

    rows = anchors + generated
    with CSV_PATH.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)

    print(f"wrote {CSV_PATH} — {len(rows)} clinicians "
          f"({len(anchors)} curated anchors + {len(generated)} generated)")


if __name__ == "__main__":
    main()

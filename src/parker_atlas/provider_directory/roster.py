"""
On-demand synthetic clinician-roster generation.

The shipped roster (`references/tables/practitioners.csv`, 150 curated + generated
clinicians) is the deterministic default. This module extends it to an arbitrary
size so the Plan-Net directory (and the dev API / web generator) can produce a
synthetic provider directory of any requested size — the same primitives the
build-time `scripts/expand_provider_roster.py` uses.

`synthesize_roster(count, seed)`:
- ``count is None`` → the shipped roster verbatim.
- ``count <= len(shipped)`` → the first ``count`` shipped rows.
- ``count > len(shipped)`` → all shipped rows plus deterministically-generated
  clinicians (valid NPPES NPIs continuing the sequence, distinct names,
  apportioned across specialties) up to ``count``.

Every generated NPI is a valid 10-digit individual NPI (NPPES Luhn check digit
over the "80840" issuer prefix). Deterministic: same ``count`` + ``seed`` →
identical rows.
"""

from __future__ import annotations

import random

from parker_atlas.references import PractitionerRow, load_practitioners

DEFAULT_SEED = 20260713

# Given / family name pools — large enough that a several-hundred-clinician roster
# reads as distinct people. Synthetic, license-clean.
GIVEN = (
    "Aaron", "Priya", "Marcus", "Wei", "Sofia", "Diego", "Amara", "Noah",
    "Leila", "Omar", "Hana", "Ethan", "Yuki", "Carlos", "Nadia", "Ivan",
    "Grace", "Tariq", "Elena", "Kofi", "Mira", "Sean", "Ingrid", "Rohan",
    "Beatriz", "Lars", "Aisha", "Felix", "Ling", "Mateus", "Zara", "Oscar",
    "Freya", "Nikolai", "Imani", "Andre", "Sana", "Viktor", "Lucia", "Kai",
    "Rania", "Pedro", "Anja", "Malik", "Chiara", "Tomas", "Nia", "Bjorn",
    "Farah", "Dmitri", "Elsa", "Hugo", "Meera", "Soren", "Ana", "Rafael",
    "Yara", "Emil", "Divya", "Luka",
)
FAMILY = (
    "Abbott", "Bianchi", "Cho", "Diaz", "Espinoza", "Farrell", "Gupta",
    "Haas", "Ibrahim", "Jansen", "Kovac", "Lindqvist", "Mahmoud", "Nakamura",
    "Ortega", "Pappas", "Quintero", "Reddy", "Saito", "Toledo", "Ustinov",
    "Vasquez", "Walsh", "Xu", "Yildiz", "Zheng", "Baptiste", "Castillo",
    "Duarte", "Egorov", "Ferreira", "Grigoryan", "Hoffman", "Ismail",
    "Johansen", "Krishnan", "Laurent", "Moreau", "Ndiaye", "Okonkwo",
    "Petersen", "Rahman", "Solberg", "Tremblay", "Ueda", "Voss", "Weiss",
    "Yoon", "Zamora", "Adebayo", "Beckett", "Contreras", "Dumont", "Falk",
    "Gallardo", "Halvorsen", "Iversen", "Jindal", "Karlsson", "Lozano",
)

# Advanced-practice taxonomies carry no "Dr." prefix.
_NO_PREFIX = ("363L00000X", "363A00000X")

_PRIMARY = ("2000000036", "2000000044", "2000000051")

# Specialty catalog: (taxonomy_code, display, encounter_class, facilities, weight).
# `weight` drives how many *additional* clinicians land in each specialty
# (largest-remainder apportionment). Facilities are rotated for a realistic
# site spread; every NPI here exists in locations.csv.
CATALOG: tuple[tuple[str, str, str, tuple[str, ...], int], ...] = (
    ("207R00000X", "Internal Medicine", "AMB", _PRIMARY, 22),
    ("207Q00000X", "Family Medicine", "AMB", ("2000000036", "2000000044"), 18),
    ("363L00000X", "Nurse Practitioner", "AMB",
     ("2000000036", "2000000044", "2000000069", "2000000051"), 15),
    ("208000000X", "Pediatrics", "AMB", ("2000000069",), 9),
    ("363A00000X", "Physician Assistant", "AMB",
     ("2000000036", "2000000044", "2000000085"), 9),
    ("207P00000X", "Emergency Medicine", "EMER", ("2000000010",), 6),
    ("208M00000X", "Hospitalist", "IMP", ("2000000010",), 6),
    ("207V00000X", "Obstetrics & Gynecology", "AMB", ("2000000069",), 5),
    ("2084P0800X", "Psychiatry", "AMB", ("2000000077",), 5),
    ("207RC0000X", "Cardiovascular Disease", "AMB", ("2000000028",), 4),
    ("2085R0202X", "Diagnostic Radiology", "AMB", ("2000000093",), 4),
    ("207L00000X", "Anesthesiology", "IMP", ("2000000010",), 4),
    ("2084N0400X", "Neurology", "AMB", ("2000000077",), 3),
    ("207N00000X", "Dermatology", "AMB", ("2000000051",), 3),
    ("207X00000X", "Orthopaedic Surgery", "IMP", ("2000000085",), 3),
    ("207RG0100X", "Gastroenterology", "AMB", ("2000000051",), 2),
    ("208600000X", "Surgery", "IMP", ("2000000085",), 2),
    ("207W00000X", "Ophthalmology", "AMB", ("2000000085",), 2),
    ("207RH0003X", "Hematology & Oncology", "AMB", ("2000000101",), 2),
    ("207RE0101X", "Endocrinology Diabetes & Metabolism", "AMB", ("2000000051",), 1),
    ("207RN0300X", "Nephrology", "AMB", ("2000000051",), 1),
    ("207RP1001X", "Pulmonary Disease", "AMB", ("2000000051",), 1),
    ("207RI0200X", "Infectious Disease", "AMB", ("2000000051",), 1),
    ("207RR0500X", "Rheumatology", "AMB", ("2000000051",), 1),
    ("208800000X", "Urology", "AMB", ("2000000085",), 1),
    ("207Y00000X", "Otolaryngology", "AMB", ("2000000085",), 1),
    ("208100000X", "Physical Medicine & Rehabilitation", "AMB", ("2000000051",), 1),
    ("207RC0200X", "Critical Care Medicine", "IMP", ("2000000010",), 1),
    ("207RG0300X", "Geriatric Medicine", "AMB", ("2000000036",), 1),
    ("2085R0001X", "Radiation Oncology", "AMB", ("2000000101",), 1),
    ("207RI0011X", "Interventional Cardiology", "AMB", ("2000000028",), 1),
)


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


def generate_additional(
    base: tuple[PractitionerRow, ...], n_add: int, seed: int
) -> list[PractitionerRow]:
    """Deterministically generate ``n_add`` clinicians extending ``base``."""
    if n_add <= 0:
        return []
    max_base = max(int(r.npi[:9]) for r in base)
    counts = apportion([c[4] for c in CATALOG], n_add)
    rng = random.Random(seed)
    used_names = {(r.given, r.family) for r in base}
    rows: list[PractitionerRow] = []
    cursor = max_base
    for (tax, display, cls, facilities, _w), k in zip(CATALOG, counts, strict=True):
        for j in range(k):
            given = family = ""
            for _ in range(500):
                given = rng.choice(GIVEN)
                family = rng.choice(FAMILY)
                if (given, family) not in used_names:
                    break
            used_names.add((given, family))
            cursor += 1
            rows.append(PractitionerRow(
                npi=full_npi(str(cursor).zfill(9)),
                family=family, given=given,
                prefix="" if tax in _NO_PREFIX else "Dr.",
                taxonomy_code=tax, taxonomy_display=display,
                encounter_class=cls, facility_npi=facilities[j % len(facilities)],
            ))
    return rows


def synthesize_roster(
    count: int | None = None, seed: int = DEFAULT_SEED
) -> tuple[PractitionerRow, ...]:
    """Return a roster of ``count`` clinicians (see module docstring)."""
    base = load_practitioners()
    if count is None or count == len(base):
        return base
    if count < 1:
        raise ValueError("count must be >= 1")
    if count <= len(base):
        return base[:count]
    return base + tuple(generate_additional(base, count - len(base), seed))

"""
Bookable clinicians for SMART Scheduling Links datasets.

When clinicians are enabled, each clinic site gets a primary-care clinician
with a US Core Practitioner, a US Core PractitionerRole at that site, and their
own Schedule (``actor`` = the site's Location first, as SMART Scheduling Links
clients expect, then the PractitionerRole). The sites share one synthetic
Organization.

NPIs come from ``references/tables/scheduling_npis.csv``: Luhn-valid numbers
that the public CMS NPPES NPI Registry API reported as unassigned when pinned
(``scripts/verify_npis_nppes.py`` regenerates or re-verifies the list).
Row 0 is the Organization, row 1 is Sam Torres, the rest are rotated clinicians.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources

NUCC = "http://nucc.org/provider-taxonomy"


@dataclass(frozen=True, slots=True)
class Clinician:
    npi: str
    given: str
    family: str
    prefix: str  # "" for advanced-practice clinicians
    suffix: str  # credential, e.g. "NP", "MD"
    role_code: str  # NUCC taxonomy for PractitionerRole.code
    role_display: str
    specialty_code: str  # NUCC taxonomy for PractitionerRole.specialty
    specialty_display: str
    # SNOMED CT occupation for PractitionerRole.code (US Core Care Team Member Function).
    snomed: tuple[str, str] = ("", "")


@dataclass(frozen=True, slots=True)
class SchedulingOrganization:
    npi: str
    name: str
    phone: str


# Synthetic name pool for rotated clinicians (license-clean, not real people).
_GIVEN = ("Avery", "Jordan", "Riley", "Morgan", "Casey", "Quinn", "Rowan", "Emerson", "Hayden", "Reese", "Ellis", "Sage")
_FAMILY = ("Lindgren", "Vellacott", "Marchetti", "Quenby", "Varga", "Quill", "Ashdown", "Belcourt", "Ostrowicz", "Tanaka", "Fennimore", "Dunleavy")

# Rotation of primary-care roles (NUCC role, specialty) across sites.
_ROLES: tuple[tuple[str, str, str, str, str, str], ...] = (
    # (prefix, suffix, role_code, role_display, specialty_code, specialty_display)
    ("Dr.", "MD", "207Q00000X", "Family Medicine Physician", "207Q00000X", "Family Medicine Physician"),
    ("", "NP", "363L00000X", "Nurse Practitioner", "363LF0000X", "Family Nurse Practitioner"),
    ("Dr.", "MD", "207R00000X", "Internal Medicine Physician", "207R00000X", "Internal Medicine Physician"),
    ("", "PA-C", "363A00000X", "Physician Assistant", "363AM0700X", "Medical Physician Assistant"),
)

# The clinic site (index into CLINIC_SITES) where Sam Torres practises.
SAM_TORRES_SITE = 31  # Denver, CO


# NUCC role -> SNOMED CT occupation.
SNOMED_OCCUPATION: dict[str, tuple[str, str]] = {
    "363L00000X": ("224571005", "Nurse practitioner"),
    "363A00000X": ("449161006", "Physician assistant"),
    "207Q00000X": ("62247001", "Family medicine specialist"),
    "207R00000X": ("158967008", "Consultant physician"),
}


@lru_cache(maxsize=1)
def _pinned_npis() -> tuple[str, ...]:
    with resources.files("parker_atlas.references.tables").joinpath("scheduling_npis.csv").open(encoding="utf-8") as fh:
        return tuple(row["npi"] for row in csv.DictReader(fh))


def scheduling_organization() -> SchedulingOrganization:
    return SchedulingOrganization(npi=_pinned_npis()[0], name="Apex Atlas Community Health", phone="1-800-555-2700")


def sam_torres() -> Clinician:
    """Sam Torres, NP: family nurse practitioner (synthetic)."""
    return Clinician(
        npi=_pinned_npis()[1],
        given="Sam",
        family="Torres",
        prefix="",
        suffix="NP",
        role_code="363L00000X",
        role_display="Nurse Practitioner",
        specialty_code="363LF0000X",
        specialty_display="Family Nurse Practitioner",
        snomed=SNOMED_OCCUPATION["363L00000X"],
    )


def clinician_for_site(site_index: int) -> Clinician:
    """The bookable clinician at a clinic site (deterministic)."""
    if site_index == SAM_TORRES_SITE:
        return sam_torres()
    npis = _pinned_npis()[2:]
    if site_index >= len(npis):
        raise ValueError(f"no pinned NPI for site {site_index}; extend scheduling_npis.csv")
    prefix, suffix, rc, rd, sc, sd = _ROLES[site_index % len(_ROLES)]
    return Clinician(
        npi=npis[site_index],
        given=_GIVEN[site_index % len(_GIVEN)],
        # Shift the family pool every full pass of given names, so all 40 names are distinct.
        family=_FAMILY[(site_index * 7 + site_index // len(_GIVEN) + 3) % len(_FAMILY)],
        prefix=prefix,
        suffix=suffix,
        role_code=rc,
        role_display=rd,
        specialty_code=sc,
        specialty_display=sd,
        snomed=SNOMED_OCCUPATION[rc],
    )

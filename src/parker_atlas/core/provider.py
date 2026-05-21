"""
Care-team sampling: pick a Practitioner + Location for an Encounter.

The reference roster (practitioners.csv / locations.csv) tags each
clinician with the v3-ActCode encounter class they typically staff
(AMB, EMER, IMP, ...) and each Location with a facility_role
(hosp | prov). Sampling picks uniformly within the subset matching the
encounter class. If no clinician matches the class, the sampler falls
back to ambulatory (AMB) — every clinician is at least credentialed
for outpatient work.

The returned `CareTeam` is the minimum needed to wire an Encounter:
- one Practitioner (NPI, name, taxonomy)
- one Location (and its facility Organization, by NPI)

Higher-level construction (PractitionerRole, Organization, Location
FHIR resources) lives in the corresponding `fhir/` modules.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from parker_atlas.references import (
    LocationRow,
    PractitionerRow,
    load_locations,
    load_practitioners,
)

_AMB = "AMB"


@dataclass(frozen=True, slots=True)
class CareTeam:
    practitioner: PractitionerRow
    location: LocationRow


def _practitioners_for_class(class_code: str) -> tuple[PractitionerRow, ...]:
    roster = load_practitioners()
    matched = tuple(p for p in roster if p.encounter_class == class_code)
    if matched:
        return matched
    # Fallback: any clinician credentialed for ambulatory is acceptable
    # for outpatient-equivalent encounters (VR, HH).
    return tuple(p for p in roster if p.encounter_class == _AMB) or roster


def _locations_for_class(class_code: str) -> tuple[LocationRow, ...]:
    roster = load_locations()
    if class_code == "IMP":
        matched = tuple(
            loc for loc in roster if loc.location_type_code == "HOSP"
        )
    elif class_code == "EMER":
        matched = tuple(loc for loc in roster if loc.location_type_code == "ER")
    else:
        matched = tuple(loc for loc in roster if loc.location_type_code == "OF")
    return matched or roster


def sample_care_team(rng: random.Random, *, class_code: str) -> CareTeam:
    """Pick a Practitioner + Location plausible for the encounter class."""
    practitioners = _practitioners_for_class(class_code)
    locations = _locations_for_class(class_code)
    return CareTeam(
        practitioner=rng.choice(practitioners),
        location=rng.choice(locations),
    )

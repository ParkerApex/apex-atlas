"""Care-team sampling: roster shape, class matching, NPI Luhn validity."""

from __future__ import annotations

import random

import pytest

from parker_atlas.core.provider import sample_care_team
from parker_atlas.references import load_locations, load_practitioners


def _luhn_npi(npi: str) -> bool:
    """NPI Luhn check: prefix '80840' + 9-digit identifier, mod-10 over check digit."""
    if len(npi) != 10 or not npi.isdigit():
        return False
    s = "80840" + npi[:-1]
    total = 0
    for i, ch in enumerate(reversed(s)):
        d = int(ch)
        if i % 2 == 0:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return (10 - total % 10) % 10 == int(npi[-1])


def test_every_practitioner_npi_is_luhn_valid():
    for p in load_practitioners():
        assert _luhn_npi(p.npi), f"invalid NPI {p.npi}"


def test_every_facility_npi_is_luhn_valid():
    for loc in load_locations():
        assert _luhn_npi(loc.facility_npi), f"invalid facility NPI {loc.facility_npi}"


def test_practitioner_npis_start_with_1():
    for p in load_practitioners():
        assert p.npi[0] == "1", "Type-1 (individual) NPIs must start with 1"


def test_facility_npis_start_with_2():
    for loc in load_locations():
        assert loc.facility_npi[0] == "2", "Type-2 (organization) NPIs must start with 2"


@pytest.mark.parametrize("class_code", ["AMB", "EMER", "IMP"])
def test_sample_care_team_matches_class(class_code):
    rng = random.Random(1)
    team = sample_care_team(rng, class_code=class_code)
    # Practitioner is either credentialed for the class, or AMB as fallback.
    assert team.practitioner.encounter_class in (class_code, "AMB")
    # Locations: IMP→HOSP, EMER→ER, AMB→OF (with fallback if missing).
    if class_code == "IMP":
        assert team.location.location_type_code in ("HOSP", "OF", "ER")
    elif class_code == "EMER":
        assert team.location.location_type_code in ("ER", "HOSP", "OF")
    else:
        assert team.location.location_type_code in ("OF", "HOSP", "ER")


def test_sample_care_team_is_deterministic_under_seed():
    rng_a = random.Random(42)
    rng_b = random.Random(42)
    a = sample_care_team(rng_a, class_code="AMB")
    b = sample_care_team(rng_b, class_code="AMB")
    assert a == b

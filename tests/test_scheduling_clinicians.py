"""Bookable clinicians in SMART Scheduling Links datasets (Practitioner + PractitionerRole + per-clinician Schedule)."""

from __future__ import annotations

import json
from datetime import date

from parker_atlas.provider_directory.roster import npi_check_digit
from parker_atlas.scheduling import SchedulingConfig, generate_scheduling_dataset, write_bulk_publish
from parker_atlas.scheduling.clinicians import SAM_TORRES_SITE, clinician_for_site, sam_torres

NUCC = "http://nucc.org/provider-taxonomy"


def _dataset(**kw):
    cfg = SchedulingConfig(
        sites=40,
        service_keys=("general-practice", "immunization"),
        window_start=date(2026, 11, 2),
        weeks=1,
        seed=7,
        clinicians=True,
        booking_base_url="https://demo.parkerapex.com/book",
        **kw,
    )
    return generate_scheduling_dataset(cfg)


def test_off_by_default_keeps_location_only_publication():
    d = generate_scheduling_dataset(SchedulingConfig(sites=3, window_start=date(2026, 11, 2), weeks=1, seed=1))
    assert not d.practitioners and not d.practitioner_roles and not d.organizations
    assert all(len(s["actor"]) == 1 and s["actor"][0]["reference"].startswith("Location/") for s in d.schedules)


def test_one_clinician_per_site_with_role_and_schedule():
    d = _dataset()
    assert len(d.practitioners) == len(d.practitioner_roles) == 40
    assert len(d.organizations) == 1
    clinician_schedules = [s for s in d.schedules if len(s["actor"]) == 2]
    assert len(clinician_schedules) == 40
    for s in clinician_schedules:
        # Location first: SMART Scheduling Links clients read actor[0] as the site.
        assert s["actor"][0]["reference"].startswith("Location/")
        assert s["actor"][1]["reference"].startswith("PractitionerRole/")


def test_sam_torres_is_a_family_nurse_practitioner_in_denver():
    d = _dataset()
    sam = sam_torres()
    prac = next(p for p in d.practitioners if p["identifier"][0]["value"] == sam.npi)
    assert prac["name"][0] == {"family": "Torres", "given": ["Sam"], "suffix": ["NP"]}
    role = next(r for r in d.practitioner_roles if r["practitioner"]["reference"] == f"Practitioner/{prac['id']}")
    assert {"system": NUCC, "code": "363L00000X", "display": "Nurse Practitioner"} in role["code"][0]["coding"]
    assert role["specialty"][0]["coding"][0]["code"] == "363LF0000X"
    assert role["telecom"] and role["availableTime"]
    loc = next(l for l in d.locations if f"Location/{l['id']}" == role["location"][0]["reference"])
    assert loc["address"]["city"] == "Denver" and SAM_TORRES_SITE == 31


def test_npis_are_valid_and_distinct():
    d = _dataset()
    npis = [p["identifier"][0]["value"] for p in d.practitioners] + [d.organizations[0]["identifier"][0]["value"]]
    assert len(set(npis)) == len(npis)
    for npi in npis:
        assert len(npi) == 10 and npi[0] in "12" and npi_check_digit(npi[:9]) == npi[9]


def test_clinician_names_are_distinct():
    names = {(clinician_for_site(i).given, clinician_for_site(i).family) for i in range(40)}
    assert len(names) == 40


def test_free_clinician_slots_carry_booking_links():
    d = _dataset()
    role_schedules = {s["id"] for s in d.schedules if len(s["actor"]) == 2}
    slots = [s for s in d.slots if s["schedule"]["reference"].split("/")[1] in role_schedules]
    assert slots and {s["status"] for s in slots} == {"free", "busy"}
    for s in slots:
        urls = {e["url"]: e for e in s["extension"]}
        link = urls["http://fhir-registry.smarthealthit.org/StructureDefinition/booking-deep-link"]["valueUrl"]
        assert link.startswith("https://demo.parkerapex.com/book/") and f"slot={s['id']}" in link
        assert "http://fhir-registry.smarthealthit.org/StructureDefinition/booking-phone" in urls


def test_manifest_lists_spec_types_first_and_references_resolve(tmp_path):
    d = _dataset()
    write_bulk_publish(d, tmp_path, base_url="https://example.org/s", transaction_time="2026-11-01T00:00:00Z")
    manifest = json.loads((tmp_path / "bulk-publish-manifest.json").read_text())
    types = [o["type"] for o in manifest["output"]]
    assert types == ["Location", "Schedule", "Slot", "Organization", "Practitioner", "PractitionerRole"]
    ids = set()
    for t in types:
        for line in (tmp_path / f"{t}.ndjson").read_text().splitlines():
            r = json.loads(line)
            ids.add(f"{r['resourceType']}/{r['id']}")
    refs = []
    for line in (tmp_path / "Schedule.ndjson").read_text().splitlines():
        refs += [a["reference"] for a in json.loads(line)["actor"]]
    for line in (tmp_path / "PractitionerRole.ndjson").read_text().splitlines():
        r = json.loads(line)
        refs += [r["practitioner"]["reference"], r["organization"]["reference"], r["location"][0]["reference"]]
    assert refs and all(ref in ids for ref in refs)

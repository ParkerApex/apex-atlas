"""Tests for the Da Vinci Plan-Net provider directory generator + publish.

Also verifies the coherence guarantee: the directory is built from the same
provider roster that patient encounters draw from, so NPIs match across claims
and the directory.
"""

from __future__ import annotations

import json

from fhir.resources.R4B.endpoint import Endpoint
from fhir.resources.R4B.healthcareservice import HealthcareService
from fhir.resources.R4B.insuranceplan import InsurancePlan
from fhir.resources.R4B.location import Location
from fhir.resources.R4B.organization import Organization
from fhir.resources.R4B.practitioner import Practitioner
from fhir.resources.R4B.practitionerrole import PractitionerRole
from typer.testing import CliRunner

from parker_atlas.cli import app
from parker_atlas.fhir.plannet import NETWORK_REFERENCE_EXT, PLANNET_NETWORK
from parker_atlas.provider_directory import (
    build_manifest,
    generate_provider_directory,
    write_bulk_publish,
)
from parker_atlas.references import load_locations, load_practitioners

runner = CliRunner()


def _npis(resources):
    out = set()
    for r in resources:
        for ident in r.get("identifier", []):
            if ident.get("system") == "http://hl7.org/fhir/sid/us-npi":
                out.add(ident["value"])
    return out


class TestGeneration:
    def test_reflects_the_roster(self):
        d = generate_provider_directory()
        assert len(d.practitioners) == len(load_practitioners())
        assert len(d.locations) == len(load_locations())
        # 2 networks + one Organization per unique facility NPI.
        n_facilities = len({loc.facility_npi for loc in load_locations()})
        assert d.counts["Organization"] == 2 + n_facilities
        assert d.counts["InsurancePlan"] == 2

    def test_all_resources_validate(self):
        d = generate_provider_directory()
        for r in d.organizations:
            Organization(**r)
        for r in d.locations:
            Location(**r)
        for r in d.practitioners:
            Practitioner(**r)
        for r in d.practitioner_roles:
            PractitionerRole(**r)
        for r in d.healthcare_services:
            HealthcareService(**r)
        for r in d.insurance_plans:
            InsurancePlan(**r)
        for r in d.endpoints:
            Endpoint(**r)

    def test_two_networks_present(self):
        d = generate_provider_directory()
        nets = [o for o in d.organizations if PLANNET_NETWORK in o["meta"]["profile"]]
        assert len(nets) == 2

    def test_practitioner_npis_match_roster(self):
        d = generate_provider_directory()
        assert _npis(d.practitioners) == {p.npi for p in load_practitioners()}

    def test_facility_npis_match_roster(self):
        d = generate_provider_directory()
        facility_orgs = [o for o in d.organizations if PLANNET_NETWORK not in o["meta"]["profile"]]
        assert _npis(facility_orgs) == {loc.facility_npi for loc in load_locations()}

    def test_practitioner_role_references_resolve(self):
        d = generate_provider_directory()
        ids = {
            r["id"]
            for group in (d.organizations, d.locations, d.practitioners, d.healthcare_services)
            for r in group
        }
        for role in d.practitioner_roles:
            for ref in (
                role["practitioner"]["reference"],
                role["organization"]["reference"],
                role["location"][0]["reference"],
                role["healthcareService"][0]["reference"],
                role["extension"][0]["valueReference"]["reference"],
            ):
                assert ref.split("/", 1)[1] in ids, ref

    def test_role_has_network_extension(self):
        d = generate_provider_directory()
        for role in d.practitioner_roles:
            assert any(e["url"] == NETWORK_REFERENCE_EXT for e in role["extension"])


class TestManifestAndPublish:
    def test_manifest_lists_present_types(self):
        d = generate_provider_directory()
        m = build_manifest(d, base_url="https://x/pd/", transaction_time="2026-07-12T00:00:00Z")
        assert m["request"] == "https://x/pd/$bulk-publish"
        types = [o["type"] for o in m["output"]]
        assert types[0] == "Organization"
        assert "PractitionerRole" in types and "Endpoint" in types

    def test_write_bulk_publish(self, tmp_path):
        d = generate_provider_directory()
        mp = write_bulk_publish(d, tmp_path, base_url="https://x/pd", transaction_time="2026-07-12T00:00:00Z")
        assert mp.exists()
        # Entry point also published at the literal `$bulk-publish` path so it
        # resolves on static hosting (GitHub raw), not only the live API.
        assert (tmp_path / "$bulk-publish").read_text() == mp.read_text()
        for t in ("Organization", "Location", "Practitioner", "PractitionerRole", "HealthcareService", "InsurancePlan", "Endpoint"):
            assert (tmp_path / f"{t}.ndjson").read_text().strip()


class TestCoherenceWithEncounters:
    def test_encounter_practitioner_npis_are_in_directory(self, tmp_path):
        # Generate a cohort with providers; every Practitioner NPI it emits must
        # appear in the published Plan-Net directory.
        result = runner.invoke(
            app,
            ["generate", "--patients", "60", "--seed", "7", "--as-of", "2026-04-25",
             "--module", "hypertension,diabetes", "--with-providers",
             "--format", "ndjson", "--out", str(tmp_path)],
        )
        assert result.exit_code == 0, result.output
        prac_file = tmp_path / "Practitioner.ndjson"
        assert prac_file.exists()
        encounter_npis = _npis(
            json.loads(x) for x in prac_file.read_text().splitlines() if x
        )
        assert encounter_npis  # providers were emitted
        directory_npis = _npis(generate_provider_directory().practitioners)
        assert encounter_npis <= directory_npis


class TestCli:
    def test_publish_provider_directory(self, tmp_path):
        out = tmp_path / "pd"
        result = runner.invoke(app, ["publish-provider-directory", "--out", str(out)])
        assert result.exit_code == 0, result.output
        manifest = json.loads((out / "bulk-publish-manifest.json").read_text())
        assert next(o["type"] for o in manifest["output"]) == "Organization"

    def test_publish_provider_directory_count(self, tmp_path):
        out = tmp_path / "pd"
        result = runner.invoke(
            app, ["publish-provider-directory", "--count", "300", "--out", str(out)]
        )
        assert result.exit_code == 0, result.output
        lines = (out / "Practitioner.ndjson").read_text().splitlines()
        assert len([ln for ln in lines if ln.strip()]) == 300


class TestOnDemandCount:
    def test_default_is_shipped_roster(self):
        from parker_atlas.references import load_practitioners

        d = generate_provider_directory()
        assert len(d.practitioners) == len(load_practitioners())

    def test_smaller_count_truncates(self):
        d = generate_provider_directory(count=25)
        assert len(d.practitioners) == 25
        assert len(d.practitioner_roles) == 25

    def test_larger_count_synthesizes_valid_unique_npis(self):
        from parker_atlas.provider_directory.roster import npi_check_digit

        d = generate_provider_directory(count=500)
        npis = [p["identifier"][0]["value"] for p in d.practitioners]
        assert len(npis) == 500
        assert len(set(npis)) == 500  # unique
        for npi in npis:
            assert len(npi) == 10 and npi[0] == "1"
            assert npi[:9] + npi_check_digit(npi[:9]) == npi  # valid check digit

    def test_deterministic_in_count_and_seed(self):
        a = generate_provider_directory(count=300, seed=7)
        b = generate_provider_directory(count=300, seed=7)
        assert [p["id"] for p in a.practitioners] == [p["id"] for p in b.practitioners]

    def test_roles_resolve_to_practitioners(self):
        d = generate_provider_directory(count=400)
        pids = {p["id"] for p in d.practitioners}
        for role in d.practitioner_roles:
            assert role["practitioner"]["reference"].split("/", 1)[1] in pids


class TestFacilityPlacement:
    def test_each_practitioner_listed_at_roster_facility(self):
        from parker_atlas.references import load_practitioners

        d = generate_provider_directory()
        org_npi_by_id = {}
        for o in d.organizations:
            for ident in o.get("identifier", []):
                if ident.get("system") == "http://hl7.org/fhir/sid/us-npi":
                    org_npi_by_id[o["id"]] = ident["value"]
        prac_npi_by_id = {p["id"]: p["identifier"][0]["value"] for p in d.practitioners}
        npi_to_facility = {p.npi: p.facility_npi for p in load_practitioners()}
        for role in d.practitioner_roles:
            pid = role["practitioner"]["reference"].split("/", 1)[1]
            oid = role["organization"]["reference"].split("/", 1)[1]
            assert org_npi_by_id[oid] == npi_to_facility[prac_npi_by_id[pid]]

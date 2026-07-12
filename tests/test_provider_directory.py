"""Tests for the Da Vinci Plan-Net provider directory generator + publish."""

from __future__ import annotations

import json

import pytest
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
    DirectoryConfig,
    build_manifest,
    generate_provider_directory,
    write_bulk_publish,
)

runner = CliRunner()


def _dir(sites=5, ppl=3):
    return generate_provider_directory(
        DirectoryConfig(sites=sites, practitioners_per_site=ppl)
    )


class TestGeneration:
    def test_counts(self):
        d = _dir(sites=5, ppl=3)
        c = d.counts
        assert c["Organization"] == 5 + 2       # provider orgs + 2 networks
        assert c["Location"] == 5
        assert c["Practitioner"] == 15
        assert c["PractitionerRole"] == 15
        assert c["Endpoint"] == 5
        assert c["InsurancePlan"] == 2

    def test_all_resources_validate(self):
        d = _dir()
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
        d = _dir()
        networks = [
            o for o in d.organizations if PLANNET_NETWORK in o["meta"]["profile"]
        ]
        assert len(networks) == 2

    def test_practitioner_role_references_resolve(self):
        d = _dir()
        ids = {
            r["id"]
            for group in (
                d.organizations, d.locations, d.practitioners,
                d.healthcare_services,
            )
            for r in group
        }
        for role in d.practitioner_roles:
            refs = [
                role["practitioner"]["reference"],
                role["organization"]["reference"],
                role["location"][0]["reference"],
                role["healthcareService"][0]["reference"],
                role["extension"][0]["valueReference"]["reference"],
            ]
            for ref in refs:
                assert ref.split("/", 1)[1] in ids, ref

    def test_role_has_network_extension(self):
        d = _dir()
        for role in d.practitioner_roles:
            assert any(e["url"] == NETWORK_REFERENCE_EXT for e in role["extension"])

    @pytest.mark.parametrize("kw", [{"sites": 0}, {"sites": 999}, {"practitioners_per_site": 0}])
    def test_invalid_config_raises(self, kw):
        with pytest.raises(ValueError):
            generate_provider_directory(DirectoryConfig(**kw))


class TestManifestAndPublish:
    def test_manifest_lists_present_types(self):
        d = _dir()
        m = build_manifest(d, base_url="https://x/pd/", transaction_time="2026-07-12T00:00:00Z")
        assert m["request"] == "https://x/pd/$bulk-publish"
        types = [o["type"] for o in m["output"]]
        assert types[0] == "Organization"
        assert "PractitionerRole" in types and "Endpoint" in types

    def test_write_bulk_publish(self, tmp_path):
        d = _dir()
        mp = write_bulk_publish(d, tmp_path, base_url="https://x/pd", transaction_time="2026-07-12T00:00:00Z")
        assert mp.exists()
        for t in ("Organization", "Location", "Practitioner", "PractitionerRole", "HealthcareService", "InsurancePlan", "Endpoint"):
            assert (tmp_path / f"{t}.ndjson").read_text().strip()


class TestCli:
    def test_publish_provider_directory(self, tmp_path):
        out = tmp_path / "pd"
        result = runner.invoke(
            app,
            ["publish-provider-directory", "--sites", "3", "--practitioners-per-site", "2", "--out", str(out)],
        )
        assert result.exit_code == 0, result.output
        manifest = json.loads((out / "bulk-publish-manifest.json").read_text())
        assert next(o["type"] for o in manifest["output"]) == "Organization"
        roles = [json.loads(x) for x in (out / "PractitionerRole.ndjson").read_text().splitlines() if x]
        assert len(roles) == 6

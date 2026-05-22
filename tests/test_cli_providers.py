"""End-to-end --with-providers: encounter wiring + cross-bundle dedup."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from parker_atlas.cli import app

runner = CliRunner()


def _bundles(out: Path) -> list[dict]:
    return [
        json.loads(p.read_text())
        for p in sorted(out.glob("*.json"))
        if p.name != "generation-metadata.json"
    ]


def _resources(bundle: dict, rtype: str) -> list[dict]:
    return [e["resource"] for e in bundle["entry"] if e["resource"]["resourceType"] == rtype]


def test_with_providers_attaches_participant_location_serviceprovider(tmp_path):
    result = runner.invoke(
        app,
        [
            "generate",
            "--patients",
            "20",
            "--seed",
            "11",
            "--module",
            "hypertension,ischemic_heart_disease",
            "--with-providers",
            "--out",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0, result.output

    bundles = _bundles(tmp_path)
    encs_with_participants = 0
    for b in bundles:
        for enc in _resources(b, "Encounter"):
            if "participant" in enc:
                encs_with_participants += 1
                indiv_url = enc["participant"][0]["individual"]["reference"]
                resolved = [
                    e for e in b["entry"]
                    if e["fullUrl"] == indiv_url
                    and e["resource"]["resourceType"] == "Practitioner"
                ]
                assert resolved, f"unresolved participant ref {indiv_url}"
                loc_url = enc["location"][0]["location"]["reference"]
                assert any(e["fullUrl"] == loc_url for e in b["entry"])
                sp_url = enc["serviceProvider"]["reference"]
                assert any(e["fullUrl"] == sp_url for e in b["entry"])

    assert encs_with_participants > 0, "no encounters got providers attached"


def test_with_providers_ndjson_dedupes_across_patients(tmp_path):
    result = runner.invoke(
        app,
        [
            "generate",
            "--patients",
            "30",
            "--seed",
            "11",
            "--module",
            "hypertension,ischemic_heart_disease",
            "--with-providers",
            "--format",
            "ndjson",
            "--out",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0, result.output

    for rtype in ("Practitioner", "PractitionerRole", "Location", "Organization"):
        p = tmp_path / f"{rtype}.ndjson"
        if not p.exists():
            continue
        ids = [json.loads(line)["id"] for line in p.read_text().splitlines() if line]
        assert len(ids) == len(set(ids)), f"{rtype}.ndjson has duplicate ids"


def test_without_providers_flag_omits_provider_resources(tmp_path):
    result = runner.invoke(
        app,
        [
            "generate",
            "--patients",
            "5",
            "--seed",
            "11",
            "--module",
            "hypertension",
            "--out",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0, result.output

    for b in _bundles(tmp_path):
        for enc in _resources(b, "Encounter"):
            assert "participant" not in enc
            assert "location" not in enc
            assert "serviceProvider" not in enc
        assert not _resources(b, "Practitioner")
        assert not _resources(b, "PractitionerRole")
        assert not _resources(b, "Location")

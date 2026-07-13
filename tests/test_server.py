"""Integration tests for the `atlas serve` dev API server.

Starts the real server on an ephemeral port in a background thread and drives
it over HTTP with urllib — no new test dependencies.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request

import pytest

from parker_atlas.server import serve


@pytest.fixture()
def server():
    httpd = serve("127.0.0.1", 0)  # ephemeral port
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    host, port = httpd.server_address
    base = f"http://{host}:{port}"
    try:
        yield base
    finally:
        httpd.shutdown()
        t.join(timeout=5)


def _get(url, timeout=60):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.status, r.headers, r.read().decode("utf-8")


def _post(url, timeout=120):
    req = urllib.request.Request(url, method="POST", data=b"")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read().decode("utf-8")


class TestBasicEndpoints:
    def test_health(self, server):
        status, _, body = _get(f"{server}/health")
        assert status == 200
        assert json.loads(body)["status"] == "ok"

    def test_modules(self, server):
        status, _, body = _get(f"{server}/modules")
        assert status == 200
        data = json.loads(body)
        assert data["count"] >= 100
        assert "hypertension" in data["modules"]

    def test_metadata_is_capability_statement(self, server):
        _, _, body = _get(f"{server}/fhir/metadata")
        assert json.loads(body)["resourceType"] == "CapabilityStatement"

    def test_unknown_route_404(self, server):
        with pytest.raises(urllib.error.HTTPError) as exc:
            _get(f"{server}/nope")
        assert exc.value.code == 404

    def test_cors_headers_present(self, server):
        # A browser page on another origin must be allowed to call the API.
        _, headers, _ = _get(f"{server}/health")
        assert headers.get("Access-Control-Allow-Origin") == "*"

    def test_cors_preflight(self, server):
        req = urllib.request.Request(f"{server}/generate", method="OPTIONS")
        with urllib.request.urlopen(req, timeout=10) as r:
            assert r.status == 204
            assert r.headers.get("Access-Control-Allow-Origin") == "*"
            assert "POST" in r.headers.get("Access-Control-Allow-Methods", "")


class TestSyncGenerate:
    def test_generate_returns_ndjson_patients(self, server):
        status, body = _post(f"{server}/generate?patients=8&seed=1&modules=hypertension")
        assert status == 200
        lines = [json.loads(line) for line in body.strip().splitlines()]
        types = {r.get("resourceType") for r in lines}
        assert "Patient" in types
        n_patients = sum(1 for r in lines if r.get("resourceType") == "Patient")
        assert n_patients == 8

    def test_patient_cap_enforced(self, server, monkeypatch):
        # Request far above MAX_PATIENTS; should be capped, not error. Patch the
        # cap to a small value so the test stays fast (the handler reads the
        # module global at request time).
        import parker_atlas.server as srv

        monkeypatch.setattr(srv, "MAX_PATIENTS", 8)
        status, body = _post(f"{server}/generate?patients=999999&seed=1&modules=asthma")
        assert status == 200
        n = sum(1 for line in body.splitlines() if '"resourceType": "Patient"' in line
                or '"resourceType":"Patient"' in line)
        assert 0 < n <= 8


class TestBulkExport:
    def test_export_kickoff_poll_download(self, server):
        # Kickoff
        with urllib.request.urlopen(f"{server}/fhir/$export?patients=10&seed=2&modules=diabetes", timeout=60) as r:
            assert r.status == 202
            loc = r.headers.get("Content-Location")
            kickoff = json.loads(r.read())
        assert loc and kickoff["job"] in loc

        # Poll until complete (bounded)
        manifest = None
        for _ in range(60):
            try:
                status, _, body = _get(loc)
            except urllib.error.HTTPError as e:
                if e.code == 202:
                    time.sleep(0.5); continue
                raise
            if status == 200:
                manifest = json.loads(body); break
            time.sleep(0.5)
        assert manifest is not None, "export did not complete in time"
        assert manifest["requiresAccessToken"] is False
        types = {o["type"] for o in manifest["output"]}
        assert "Patient" in types

        # Download the Patient NDJSON
        patient_url = next(o["url"] for o in manifest["output"] if o["type"] == "Patient")
        status, _, body = _get(patient_url)
        assert status == 200
        n = len([ln for ln in body.strip().splitlines() if ln])
        assert n == 10


class TestSchedulingBulkPublish:
    def test_manifest_lists_outputs(self, server):
        status, _, body = _get(f"{server}/scheduling/$bulk-publish?sites=2&weeks=1&seed=1")
        assert status == 200
        manifest = json.loads(body)
        assert manifest["request"].endswith("/scheduling/$bulk-publish")
        assert [o["type"] for o in manifest["output"]] == ["Location", "Schedule", "Slot"]

    def test_slot_ndjson_downloads(self, server):
        status, headers, body = _get(f"{server}/scheduling/Slot.ndjson?sites=2&weeks=1&seed=1")
        assert status == 200
        assert headers.get("Content-Type") == "application/fhir+ndjson"
        lines = [ln for ln in body.strip().splitlines() if ln]
        assert lines
        first = json.loads(lines[0])
        assert first["resourceType"] == "Slot"
        assert first["schedule"]["reference"].startswith("Schedule/")

    def test_manifest_and_files_agree(self, server):
        _, _, body = _get(f"{server}/scheduling/$bulk-publish?sites=2&weeks=1&seed=5")
        manifest = json.loads(body)
        loc_url = next(o["url"] for o in manifest["output"] if o["type"] == "Location")
        status, _, body = _get(loc_url + "?sites=2&weeks=1&seed=5")
        assert status == 200
        locs = [ln for ln in body.strip().splitlines() if ln]
        assert len(locs) == 2

    def test_capability_advertises_bulk_publish(self, server):
        _, _, body = _get(f"{server}/fhir/metadata")
        ops = {o["name"] for o in json.loads(body)["rest"][0]["operation"]}
        assert "bulk-publish" in ops


class TestProviderDirectoryBulkPublish:
    def test_manifest_lists_types(self, server):
        status, _, body = _get(f"{server}/provider-directory/$bulk-publish")
        assert status == 200
        manifest = json.loads(body)
        types = [o["type"] for o in manifest["output"]]
        assert types[0] == "Organization"
        assert "PractitionerRole" in types and "Endpoint" in types

    def test_practitionerrole_ndjson(self, server):
        status, headers, body = _get(f"{server}/provider-directory/PractitionerRole.ndjson")
        assert status == 200
        assert headers.get("Content-Type") == "application/fhir+ndjson"
        rows = [ln for ln in body.strip().splitlines() if ln]
        assert rows and json.loads(rows[0])["resourceType"] == "PractitionerRole"


class TestGenerateArgsFlags:
    def test_new_flags_passthrough(self):
        from pathlib import Path

        from parker_atlas.server import _generate_args

        qs = {
            "patients": ["5"], "seed": ["1"], "coverage": ["1"], "providers": ["1"],
            "carin_bb": ["1"], "as_of": ["2026-04-25"], "ref_style": ["relative"],
        }
        argv, _ = _generate_args(qs, Path("/tmp/x"))
        for expect in ("--with-coverage", "--with-providers", "--carin-bb",
                       "--as-of", "2026-04-25", "--ref-style", "relative"):
            assert expect in argv

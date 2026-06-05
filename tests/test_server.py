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


class TestSyncGenerate:
    def test_generate_returns_ndjson_patients(self, server):
        status, body = _post(f"{server}/generate?patients=8&seed=1&modules=hypertension")
        assert status == 200
        lines = [json.loads(line) for line in body.strip().splitlines()]
        types = {r.get("resourceType") for r in lines}
        assert "Patient" in types
        n_patients = sum(1 for r in lines if r.get("resourceType") == "Patient")
        assert n_patients == 8

    def test_patient_cap_enforced(self, server):
        # Request far above MAX_PATIENTS; should be capped, not error.
        status, body = _post(f"{server}/generate?patients=999999&seed=1&modules=asthma")
        assert status == 200
        n = sum(1 for line in body.splitlines() if '"resourceType": "Patient"' in line
                or '"resourceType":"Patient"' in line)
        assert 0 < n <= 5000


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

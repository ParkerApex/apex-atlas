"""
Apex Atlas dev API server (`atlas serve`).

A small, dependency-free HTTP server (Python stdlib only) that exposes the
generator over HTTP. It's the foundation for an on-demand / in-browser
generator and a convenient way to script cohort generation from any language.

**This is a development server, not a production deployment.** It is
single-process, keeps job state in memory, runs `atlas generate` as a
subprocess per request, and enforces a small patient cap. It is not hardened
for untrusted input or concurrency at scale, and it implements a pragmatic
subset of the FHIR Bulk Data ($export) flow — enough to kick off a job, poll
it, and download NDJSON, not the full specification (no auth, no `_since`,
no partial-results semantics).

Endpoints
---------
GET  /health                      → {"status":"ok","version":...}
GET  /modules                     → {"modules":[...]}            (bundled module names)
GET  /fhir/metadata               → minimal CapabilityStatement-ish JSON
POST /generate?<params>           → synchronous; streams application/fhir+ndjson
GET  /fhir/$export?<params>       → 202 kickoff; Content-Location: /jobs/<id>
GET  /jobs/<id>                    → 202 (in progress) | 200 Bulk Data manifest
GET  /jobs/<id>/<Type>.ndjson     → the per-resource-type NDJSON file
GET  /scheduling/$bulk-publish     → SMART Scheduling Links manifest
GET  /scheduling/<Type>.ndjson    → Location/Schedule/Slot NDJSON (deterministic)
GET  /provider-directory/$bulk-publish → Da Vinci Plan-Net directory manifest
GET  /provider-directory/<Type>.ndjson → Plan-Net directory NDJSON

Params (query string): patients (int, capped), seed (int), modules (csv),
sdoh / coverage / measures / notes / providers / carin_bb (bool: "1"/"true"),
as_of (ISO date), ref_style ("relative"|"urn-uuid"). Scheduling params:
sites (int, capped), weeks (int, capped), seed (int), services (csv).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from parker_atlas import __version__
from parker_atlas.modules.runtime import list_bundled_modules

MAX_PATIENTS = 5000
DEFAULT_PATIENTS = 100
# Dev-server caps for on-demand SMART Scheduling Links generation.
SCHED_MAX_SITES = 10
SCHED_MAX_WEEKS = 4
# Per-request generation timeout (seconds) so one request can't hang a hosted
# instance. Overridable via ATLAS_GEN_TIMEOUT.
GEN_TIMEOUT = int(os.environ.get("ATLAS_GEN_TIMEOUT", "180"))

# job_id -> {"status": "in-progress"|"complete"|"error", "dir": Path|None,
#            "manifest": dict|None, "error": str|None, "request": str}
_JOBS: dict[str, dict] = {}
_JOBS_LOCK = threading.Lock()


def _bool(qs: dict, key: str) -> bool:
    return qs.get(key, [""])[0].lower() in ("1", "true", "yes")


def _generate_args(qs: dict, out: Path) -> tuple[list[str], str]:
    """Build the `atlas generate` argv from query params. Returns (argv, summary)."""
    patients = min(int(qs.get("patients", [DEFAULT_PATIENTS])[0] or DEFAULT_PATIENTS), MAX_PATIENTS)
    seed = int(qs.get("seed", ["0"])[0] or 0)
    argv = [
        sys.executable, "-m", "parker_atlas.cli", "generate",
        "--patients", str(patients), "--seed", str(seed),
        "--format", "ndjson", "--out", str(out),
    ]
    modules = (qs.get("modules", [""])[0] or "").strip()
    if modules:
        argv += ["--module", modules]
    for flag in ("sdoh", "coverage", "measures", "notes", "providers"):
        if _bool(qs, flag):
            argv.append(f"--with-{flag}")
    if _bool(qs, "carin_bb"):
        argv.append("--carin-bb")
    as_of = (qs.get("as_of", [""])[0] or "").strip()
    if as_of:
        argv += ["--as-of", as_of]
    ref_style = (qs.get("ref_style", [""])[0] or "").strip()
    if ref_style in ("relative", "urn-uuid"):
        argv += ["--ref-style", ref_style]
    summary = f"patients={patients} seed={seed} modules={modules or '(default)'}"
    return argv, summary


def _run_generate(qs: dict, out: Path) -> None:
    argv, _ = _generate_args(qs, out)
    try:
        res = subprocess.run(argv, capture_output=True, text=True, timeout=GEN_TIMEOUT)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"generation timed out after {GEN_TIMEOUT}s") from exc
    if res.returncode != 0:
        raise RuntimeError(res.stderr[-500:] or "generation failed")


def _ndjson_files(d: Path) -> list[Path]:
    return sorted(p for p in d.glob("*.ndjson"))


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class AtlasHandler(BaseHTTPRequestHandler):
    server_version = f"AtlasDevServer/{__version__}"

    # -- helpers --------------------------------------------------------------
    def _cors_headers(self) -> None:
        # Permissive CORS so a static page (landing page / generator UI) served
        # from any origin can call this dev server. Dev-only convenience.
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Expose-Headers", "Content-Location")

    def do_OPTIONS(self) -> None:  # noqa: N802 - CORS preflight
        self.send_response(204)
        self._cors_headers()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _send_json(self, code: int, payload: dict, extra_headers: dict | None = None) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._cors_headers()
        for k, v in (extra_headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _send_ndjson(self, body: bytes) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "application/fhir+ndjson")
        self.send_header("Content-Length", str(len(body)))
        self._cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _base_url(self) -> str:
        host = self.headers.get("Host") or f"{self.server.server_address[0]}:{self.server.server_address[1]}"
        return f"http://{host}"

    def log_message(self, *_args) -> None:  # quiet by default
        pass

    # -- routing --------------------------------------------------------------
    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path, qs = parsed.path.rstrip("/") or "/", parse_qs(parsed.query)
        if path == "/health":
            return self._send_json(200, {"status": "ok", "version": __version__})
        if path == "/modules":
            return self._send_json(200, {"count": len(list_bundled_modules()),
                                         "modules": list_bundled_modules()})
        if path == "/fhir/metadata":
            return self._send_json(200, self._capability())
        if path == "/fhir/$export":
            return self._kickoff_export(qs)
        if path.startswith("/jobs/"):
            return self._jobs_route(path)
        if path == "/scheduling/$bulk-publish":
            return self._scheduling_manifest(qs)
        if path.startswith("/scheduling/") and path.endswith(".ndjson"):
            return self._scheduling_file(path, qs)
        if path == "/provider-directory/$bulk-publish":
            return self._provider_directory_manifest()
        if path.startswith("/provider-directory/") and path.endswith(".ndjson"):
            return self._provider_directory_file(path)
        return self._send_json(404, {"error": f"no route for {path}"})

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path, qs = parsed.path.rstrip("/") or "/", parse_qs(parsed.query)
        if path == "/generate":
            return self._generate_sync(qs)
        return self._send_json(404, {"error": f"no route for POST {path}"})

    # -- handlers -------------------------------------------------------------
    def _capability(self) -> dict:
        return {
            "resourceType": "CapabilityStatement",
            "status": "active", "kind": "instance",
            "software": {"name": "Apex Atlas dev server", "version": __version__},
            "fhirVersion": "4.0.1", "format": ["application/fhir+ndjson"],
            "rest": [{"mode": "server", "operation": [{"name": "export"}, {"name": "bulk-publish"}]}],
            "_note": "Development server; pragmatic subset of FHIR Bulk Data.",
        }

    def _generate_sync(self, qs: dict) -> None:
        tmp = Path(tempfile.mkdtemp(prefix="atlas-gen-"))
        try:
            _run_generate(qs, tmp)
            lines: list[str] = []
            for f in _ndjson_files(tmp):
                lines.extend(f.read_text(encoding="utf-8").splitlines())
            body = ("\n".join(lines) + "\n").encode("utf-8")
            self._send_ndjson(body)
        except (RuntimeError, ValueError) as exc:
            self._send_json(400, {"error": str(exc)})
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def _kickoff_export(self, qs: dict) -> None:
        job_id = uuid.uuid4().hex
        _, summary = _generate_args(qs, Path("."))
        with _JOBS_LOCK:
            _JOBS[job_id] = {"status": "in-progress", "dir": None, "manifest": None,
                             "error": None, "request": summary}
        base = self._base_url()

        def _worker() -> None:
            out = Path(tempfile.mkdtemp(prefix=f"atlas-export-{job_id}-"))
            try:
                _run_generate(qs, out)
                manifest = {
                    "transactionTime": _iso_now(),
                    "request": f"{base}/fhir/$export?{urlparse(self.path).query}",
                    "requiresAccessToken": False,
                    "output": [
                        {"type": f.stem, "url": f"{base}/jobs/{job_id}/{f.name}"}
                        for f in _ndjson_files(out) if f.stem != "generation-metadata"
                    ],
                    "error": [],
                }
                with _JOBS_LOCK:
                    _JOBS[job_id].update(status="complete", dir=out, manifest=manifest)
            except Exception as exc:  # noqa: BLE001 - report any failure to the poller
                with _JOBS_LOCK:
                    _JOBS[job_id].update(status="error", error=str(exc))

        threading.Thread(target=_worker, daemon=True).start()
        self._send_json(202, {"status": "accepted", "job": job_id},
                        extra_headers={"Content-Location": f"{base}/jobs/{job_id}"})

    # -- SMART Scheduling Links ($bulk-publish) -------------------------------
    def _scheduling_config(self, qs: dict):
        from parker_atlas.scheduling import DEFAULT_SERVICE_KEYS, SchedulingConfig

        sites = min(int(qs.get("sites", ["8"])[0] or 8), SCHED_MAX_SITES)
        weeks = min(int(qs.get("weeks", ["2"])[0] or 2), SCHED_MAX_WEEKS)
        seed = int(qs.get("seed", ["0"])[0] or 0)
        services = (qs.get("services", [""])[0] or "").strip()
        keys = tuple(s.strip() for s in services.split(",") if s.strip()) or DEFAULT_SERVICE_KEYS
        cfg = SchedulingConfig(sites=sites, weeks=weeks, seed=seed, service_keys=keys)
        cfg.validate()
        return cfg

    def _scheduling_manifest(self, qs: dict) -> None:
        from parker_atlas.scheduling import build_manifest, generate_scheduling_dataset

        try:
            cfg = self._scheduling_config(qs)
        except (ValueError, TypeError) as exc:
            return self._send_json(400, {"error": str(exc)})
        dataset = generate_scheduling_dataset(cfg)
        base = f"{self._base_url()}/scheduling"
        manifest = build_manifest(dataset, base_url=base, transaction_time=_iso_now())
        self._send_json(200, manifest)

    def _scheduling_file(self, path: str, qs: dict) -> None:
        from parker_atlas.scheduling import generate_scheduling_dataset

        rtype = path.rsplit("/", 1)[-1][: -len(".ndjson")]
        try:
            cfg = self._scheduling_config(qs)
        except (ValueError, TypeError) as exc:
            return self._send_json(400, {"error": str(exc)})
        dataset = generate_scheduling_dataset(cfg)
        rows = {
            "Location": dataset.locations,
            "Schedule": dataset.schedules,
            "Slot": dataset.slots,
            "Appointment": dataset.appointments,
        }.get(rtype)
        if rows is None:
            return self._send_json(404, {"error": f"no scheduling resource {rtype!r}"})
        body = ("".join(json.dumps(r) + "\n" for r in rows)).encode("utf-8")
        self._send_ndjson(body)

    # -- Da Vinci Plan-Net provider directory ($bulk-publish) -----------------
    def _provider_directory_rows(self) -> dict:
        from parker_atlas.provider_directory import generate_provider_directory

        d = generate_provider_directory()
        return {
            "Organization": d.organizations,
            "Location": d.locations,
            "Practitioner": d.practitioners,
            "PractitionerRole": d.practitioner_roles,
            "HealthcareService": d.healthcare_services,
            "InsurancePlan": d.insurance_plans,
            "Endpoint": d.endpoints,
        }

    def _provider_directory_manifest(self) -> None:
        base = f"{self._base_url()}/provider-directory"
        rows = self._provider_directory_rows()
        self._send_json(200, {
            "transactionTime": _iso_now(),
            "request": f"{base}/$bulk-publish",
            "output": [
                {"type": t, "url": f"{base}/{t}.ndjson"} for t, v in rows.items() if v
            ],
            "error": [],
        })

    def _provider_directory_file(self, path: str) -> None:
        rtype = path.rsplit("/", 1)[-1][: -len(".ndjson")]
        rows = self._provider_directory_rows().get(rtype)
        if rows is None:
            return self._send_json(404, {"error": f"no provider-directory resource {rtype!r}"})
        body = ("".join(json.dumps(r) + "\n" for r in rows)).encode("utf-8")
        self._send_ndjson(body)

    def _jobs_route(self, path: str) -> None:
        parts = path.split("/")  # ['', 'jobs', '<id>', '<file>?']
        job_id = parts[2] if len(parts) > 2 else ""
        with _JOBS_LOCK:
            job = _JOBS.get(job_id)
        if not job:
            return self._send_json(404, {"error": "unknown job"})

        # File download: /jobs/<id>/<file>.ndjson
        if len(parts) >= 4 and parts[3]:
            if job["status"] != "complete" or job["dir"] is None:
                return self._send_json(404, {"error": "job not complete"})
            target = (Path(job["dir"]) / parts[3]).resolve()
            if Path(job["dir"]).resolve() not in target.parents or not target.is_file():
                return self._send_json(404, {"error": "no such file"})
            self._send_ndjson(target.read_bytes())
            return

        # Status / manifest
        if job["status"] == "in-progress":
            return self._send_json(202, {"status": "in-progress", "job": job_id},
                                    extra_headers={"X-Progress": "generating"})
        if job["status"] == "error":
            return self._send_json(500, {"status": "error", "error": job["error"]})
        return self._send_json(200, job["manifest"])


def serve(host: str = "127.0.0.1", port: int = 8080) -> ThreadingHTTPServer:
    """Create (and return) a running server bound to (host, port).

    Caller is responsible for `serve_forever()` / shutdown. Pass port=0 for an
    ephemeral port (used by tests).
    """
    httpd = ThreadingHTTPServer((host, port), AtlasHandler)
    return httpd

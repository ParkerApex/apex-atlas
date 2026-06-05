# Apex Atlas dev API (`atlas serve`)

A small, dependency-free HTTP server that exposes the generator over HTTP — the
foundation for an on-demand / in-browser generator and a convenient way to
script cohort generation from any language.

> **Development server, not a production deployment.** Single-process, in-memory
> job state, runs `atlas generate` as a subprocess per request, and caps the
> patient count per request. It implements a *pragmatic subset* of the FHIR Bulk
> Data `$export` flow (kickoff → poll → download NDJSON) — not the full spec (no
> auth, `_since`, `_type` filtering, or partial-result semantics). Don't expose
> it to untrusted networks.

## Run it

```bash
atlas serve --port 8080
# → Apex Atlas dev server listening on http://127.0.0.1:8080
```

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | liveness — `{"status":"ok","version":...}` |
| GET | `/modules` | bundled module names |
| GET | `/fhir/metadata` | minimal CapabilityStatement |
| POST | `/generate` | **synchronous** generation; streams `application/fhir+ndjson` |
| GET | `/fhir/$export` | **async** Bulk Data kickoff → `202` + `Content-Location` |
| GET | `/jobs/<id>` | poll: `202` while running, `200` Bulk Data manifest when done |
| GET | `/jobs/<id>/<Type>.ndjson` | download a per-resource-type NDJSON file |

### Query parameters

`patients` (int, capped at 5000), `seed` (int), `modules` (comma-separated
module names), and the boolean flags `sdoh`, `coverage`, `measures`, `notes`
(`1`/`true`).

## Examples

```bash
# Synchronous: get NDJSON straight back
curl -X POST "http://127.0.0.1:8080/generate?patients=50&seed=1&modules=hypertension,diabetes&sdoh=1"

# Async FHIR Bulk Data $export
curl -i "http://127.0.0.1:8080/fhir/\$export?patients=1000&seed=7&modules=hypertension"
#   → HTTP/1.1 202 Accepted
#     Content-Location: http://127.0.0.1:8080/jobs/<id>

curl "http://127.0.0.1:8080/jobs/<id>"          # 202 while running; 200 manifest when done
# manifest.output = [{ "type": "Patient", "url": ".../jobs/<id>/Patient.ndjson" }, ...]

curl "http://127.0.0.1:8080/jobs/<id>/Patient.ndjson"   # download
```

## Where this is headed

This first cut is the substrate for the roadmap's on-demand generation milestone:
a hardened, authenticated, fully Bulk-Data-conformant `$export` service plus a
browser UI that calls it — turning the [landing page](./index.html) "try it"
experience into live generation. See [`roadmap.md`](./roadmap.md).

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
| GET | `/scheduling/$bulk-publish` | SMART Scheduling Links manifest |
| GET | `/scheduling/<Type>.ndjson` | Location / Schedule / Slot NDJSON |
| GET | `/provider-directory/$bulk-publish` | Da Vinci Plan-Net directory manifest |
| GET | `/provider-directory/<Type>.ndjson` | Plan-Net directory NDJSON |

### Query parameters

For `/generate`: `patients` (int, capped at 5000), `seed` (int), `modules`
(comma-separated module names), `as_of` (ISO date — reproducible cohorts),
`ref_style` (`urn-uuid` | `relative`), and the boolean flags `sdoh`, `coverage`,
`providers`, `measures`, `notes`, `carin_bb` (`1`/`true`).

For `/scheduling/*`: `sites`, `weeks`, `seed`, `services`. The
`/provider-directory/*` dataset is built from the shared provider roster and
takes no parameters.

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

## Browser generator UI

[`docs/generator.html`](./generator.html) is a static page that calls this server from the browser (CORS is enabled). Run `atlas serve`, open the page (via GitHub Pages, htmlpreview, or just open the file locally), point the "API base URL" field at your server, and generate cohorts interactively with a download button. It also has a **Bulk-publish** section that pulls the SMART Scheduling Links and Da Vinci Plan-Net datasets. It uses `GET /health`, `GET /modules`, `POST /generate`, and the `/scheduling` + `/provider-directory` `$bulk-publish` endpoints.

## Deploying it

To host the API behind the web generator (Docker / Fly / Render / Cloud Run), see [`deploy.md`](./deploy.md). `atlas serve` honors `$PORT` and binds `0.0.0.0` in a container; CORS is enabled so a static page can call it.

# Deploying the Apex Atlas generator API

This makes the [web generator](./generator.html) work for visitors with **zero
local setup** — a hosted `atlas serve` that the static page calls.

> **Bring your own cloud and keys.** You deploy this to *your own* cloud account
> (Fly / Render / Cloud Run / etc.) under your own billing. **No secrets are
> baked into the image** and none are needed to run the generator: synthetic
> generation is fully deterministic and uses no AI. The only feature that needs
> an AI key is the *separate* `atlas author research` CLI command, which reads
> **your own** `ANTHROPIC_API_KEY` (or another provider's key) from the
> environment at run time — it is never bundled, and it is not exposed by this
> server. Configure such keys as your platform's secrets, never in the repo or
> image.

> **Read this first — security.** `atlas serve` is a *development* server. It has
> two built-in safeguards (a 20,000-patient cap per request and a generation
> timeout, `ATLAS_GEN_TIMEOUT`, default 600s) but **no auth, rate limiting, or
> abuse protection**. For anything public, put it behind a reverse proxy / API
> gateway with rate limiting (and ideally a WAF), keep the timeout low, and use
> scale-to-zero so an idle demo costs nothing. Treat it as a demo backend, not a
> multi-tenant service.

## Container

```bash
docker build -t apex-atlas .
docker run --rm -p 8080:8080 apex-atlas
curl http://127.0.0.1:8080/health           # {"status":"ok",...}
curl -X POST "http://127.0.0.1:8080/generate?patients=20&modules=hypertension"
```

The image installs the package (all 101 modules + reference data are bundled in
the wheel) and runs `atlas serve --host 0.0.0.0 --port ${PORT:-8080}`. Every
common PaaS injects `$PORT`; the server honors it.

## Fly.io

```bash
cp deploy/fly.toml ./fly.toml          # or: fly launch --copy-config
fly launch --no-deploy                 # first time only (creates the app)
fly deploy
```

Scale-to-zero is on (`min_machines_running = 0`); the machine wakes on the first
request. The public URL is `https://<app>.fly.dev`.

## Render

New → **Blueprint**, point at this repo (uses `deploy/render.yaml`), or New →
**Web Service** → Docker. Render builds the `Dockerfile`, injects `$PORT`, and
health-checks `/health`. Free plan sleeps when idle.

## Google Cloud Run

```bash
gcloud run deploy apex-atlas-generator --source . \
  --allow-unauthenticated --region us-central1 --memory 512Mi --timeout 300
```

Cloud Run injects `$PORT` (8080) and scales to zero by default.

## Point the web UI at your deployment

Once you have a public URL, the [generator page](./generator.html) can target it
two ways:

1. Type the URL into the **API base URL** field, or
2. Open the page with `?api=` prefilled, e.g.
   `…/generator.html?api=https://apex-atlas-generator.fly.dev`.

Make sure the deployed origin and the page origin can talk — `atlas serve`
already sends permissive CORS (`Access-Control-Allow-Origin: *`), which is fine
for a public read-only demo.

## Production hardening (next, not included here)

This scaffold is intentionally minimal. Before real traffic: front it with rate
limiting + auth, lower the patient cap, add request quotas and a per-IP budget,
run multiple replicas behind a load balancer, and move `$export` job state out
of process memory (e.g. object storage + a job queue) so downloads survive
restarts and scale horizontally.

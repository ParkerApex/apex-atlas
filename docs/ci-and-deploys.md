# CI & deployments

## Continuous integration (`.github/workflows/ci.yml`)

Runs on every push to `main`, every pull request, and on demand.

| Job | Blocking? | What it does |
| --- | --- | --- |
| `test` | **Yes** | `pytest` across Python 3.11 and 3.12 (parallelized with `-n auto`). This is the regression gate. |
| `quality` | No (advisory) | `ruff check` and `mypy src/parker_atlas`, surfaced as PR annotations. |

`ruff` and `mypy` are advisory (`continue-on-error: true`) because the codebase
carries pre-existing lint/type debt (~87 ruff, ~138 mypy findings at time of
writing). New code should be clean; once the backlog is burned down, drop
`continue-on-error` to make them blocking.

## IG conformance (`.github/workflows/ig-conformance.yml`)

Runs the **official HL7 FHIR validator** (`validator_cli.jar`) against the
shipped connectathon surfaces. GitHub-hosted runners have open egress to the
FHIR package registry (`packages.fhir.org`) and terminology server
(`tx.fhir.org`) that the validator needs at runtime — hosts that most sandboxes
block — so this is where the true IG-validated pass lives (the native
`atlas validate --ig` layer runs everywhere; the external validator needs those
hosts).

| Target (matrix) | Path | IG package |
| --- | --- | --- |
| `us-core` | `patients/examples` | `hl7.fhir.us.core#6.1.0` |
| `plan-net` | `provider-directory` | `hl7.fhir.us.davinci-pdex-plan-net#1.1.0` |
| `smart-scheduling` | `scheduling/examples` | base R4 |
| `carin-bb` | freshly generated `--carin-bb` cohort | `hl7.fhir.us.carin-bb#2.1.0` |

- **Triggers:** `workflow_dispatch`, a weekly schedule, and PRs touching the
  samples / validation / FHIR-builder / workflow paths (it's slow — it downloads
  a ~130 MB validator and the IG packages — so it does not run on every push).
- **Scope:** a representative conformance *sample* (curated example bundles + the
  full Plan-Net directory + a small C4BB cohort), **not** the whole
  168k-resource population — the HL7 validator is far too slow for that.
- **Caching:** the validator jar and `~/.fhir/packages` are cached across runs.
- **Output:** each target uploads its Markdown report + raw validator log as an
  artifact and writes its verdict to the job summary.
- **Advisory for now** (`continue-on-error`): the synthetic data has not yet been
  through the official validator, so the first runs establish a baseline of real
  US Core / C4BB / Plan-Net findings. Once a target is green, drop its
  `continue-on-error` to make it a blocking gate.

Run the same pass locally where those hosts are reachable:

```bash
curl -L -o validator_cli.jar \
  https://github.com/hapifhir/org.hl7.fhir.core/releases/latest/download/validator_cli.jar
atlas validate ./samples/cms-connectathon-2026/provider-directory --ig \
  --validator-jar ./validator_cli.jar \
  --ig-package hl7.fhir.us.davinci-pdex-plan-net#1.1.0 \
  --ig-report ./plan-net-conformance.md
```

## Deployment workflows — one-time settings required

Both deploy workflows are correct but currently fail because of **repository /
PyPI settings** that can only be set by an owner (not from code):

### GitHub Pages (`pages.yml`)

The documentation site (`docs/`) is published via GitHub Pages with
**Source: GitHub Actions** (repo **Settings → Pages → Build and deployment**).
`.github/workflows/pages.yml` uploads the static `docs/` folder as-is
(`docs/.nojekyll`, no Jekyll build) and deploys it on every change to `docs/`.

> Do **not** use GitHub's auto-suggested "Jekyll" starter workflow here — it
> builds from the repo **root** (`source: ./`), which would try to Jekyll-process
> the entire repository (including the large `samples/` folder) instead of
> `docs/`. `pages.yml` uploads `docs/` directly.
>
> Alternative: set Source to **Deploy from a branch** → `main` / `/docs` and
> delete `pages.yml` — GitHub's built-in `pages-build-deployment` then serves
> `docs/` with no custom workflow.

### PyPI publish (`publish-pypi.yml`)

Failure: `invalid-publisher: valid token, but no corresponding publisher`.

The workflow authenticates to PyPI via OIDC "Trusted Publishing"; no matching
trusted publisher is registered on PyPI. Register one at
<https://pypi.org/manage/account/publishing/> with claims matching the
workflow:

| Field | Value |
| --- | --- |
| PyPI project | `apex-atlas` |
| Owner | `ParkerApex` |
| Repository | `apex-atlas` |
| Workflow filename | `publish-pypi.yml` |
| Environment | `pypi` |

(The workflow already sets `environment: pypi` and `permissions: id-token: write`.)
Once the trusted publisher exists, publishing a GitHub Release runs the workflow
and uploads the build to PyPI.

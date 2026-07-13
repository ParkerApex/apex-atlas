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

# Contributing to Parker Atlas

Thank you for considering a contribution. Parker Atlas is built by a community of engineers, clinicians, and researchers, and we welcome both code and clinical-domain contributions.

## Types of contributions we welcome

- **Clinical modules** — disease pathways, care patterns, and preventive workflows authored by licensed healthcare professionals
- **FHIR profile implementations** — US Core, IPS, and international profile support
- **Generator improvements** — performance, fidelity, output formats
- **Statistical validation** — new reference datasets to compare synthetic output against
- **Documentation, tutorials, and examples**
- **Bug reports and reproducible test cases**

## Contributor License Agreement

All contributors must sign the Parker Atlas Contributor License Agreement (CLA) before their contributions can be merged. The CLA grants Parker Health the right to distribute contributions under both the Apache 2.0 license and the Parker Atlas Commercial License. Your copyright remains yours.

The CLA bot will prompt you on your first pull request.

## Development setup

```bash
# Clone
git clone https://github.com/parker-health/parker-atlas.git
cd parker-atlas

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate

# Install with dev dependencies
pip install -e ".[dev,llm,validation]"

# Install pre-commit hooks
pre-commit install

# Run the test suite
pytest
```

## Code style

- **Formatter and linter:** `ruff` (configured in `pyproject.toml`)
- **Type checker:** `mypy --strict`
- **Test framework:** `pytest`

Run `ruff check` and `mypy src/` before submitting a pull request. CI will enforce both.

## Clinical module contributions

Clinical modules are the heart of Parker Atlas. If you are a licensed healthcare professional contributing a module, please:

1. Follow the module authoring guide in `docs/authoring/module_dsl.md`.
2. Cite public epidemiological sources for all prevalence, incidence, and progression rates.
3. Include statistical validation expectations in the module manifest.
4. Disclose any conflicts of interest (industry affiliation, consulting relationships) in the module header.

Modules authored with LLM assistance are welcome but must be reviewed and signed off by a clinician before merge.

## Reporting security issues

Do not open public issues for security vulnerabilities. Email `security@parkerapex.com` with details. We respond within three business days.

## Code of Conduct

Parker Atlas follows the [Contributor Covenant v2.1](https://www.contributor-covenant.org/). Be respectful, be welcoming, and assume good faith.

## Questions

For general questions, open a [GitHub Discussion](https://github.com/parker-health/parker-atlas/discussions). For commercial licensing, contact `licensing@parkerapex.com`.

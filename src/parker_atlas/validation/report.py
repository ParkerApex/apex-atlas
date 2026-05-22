"""
Static HTML cohort fidelity report.

Given a directory of generated FHIR R4 Bundles (or NDJSON output), build
a single self-contained HTML file summarizing:

- Cohort size and generation provenance (path, as-of date)
- Demographics: age brackets, sex, race
- Condition prevalence across the cohort
- Fidelity harness results when a module is supplied — pass/fail per
  metric with target, actual, tolerance band, and N

The HTML is fully self-contained (inline CSS, no JS, no external
assets), so it can be opened from disk, attached to an email, or
committed to a release notes folder without any runtime dependencies.
"""

from __future__ import annotations

import html
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from parker_atlas.validation.cohort import (
    CohortReport,
    _load_cohort,
    evaluate_cohort,
)
from parker_atlas.validation.expectations import Expectation


@dataclass(frozen=True, slots=True)
class CohortDemographics:
    total_patients: int
    age_brackets: tuple[tuple[tuple[int, int], int], ...]
    sex: tuple[tuple[str, int], ...]
    conditions: tuple[tuple[str, int], ...]  # display → patient count


def _default_age_brackets() -> tuple[tuple[int, int], ...]:
    return (
        (0, 17),
        (18, 39),
        (40, 64),
        (65, 79),
        (80, 120),
    )


def _bracket_for_age(
    age: int, brackets: tuple[tuple[int, int], ...]
) -> tuple[int, int] | None:
    for lo, hi in brackets:
        if lo <= age <= hi:
            return (lo, hi)
    return None


def collect_demographics(
    path: Path,
    *,
    reference_date: date | None = None,
    brackets: tuple[tuple[int, int], ...] | None = None,
) -> CohortDemographics:
    """Walk the cohort once and tally age/sex/condition counts.

    Race is omitted today — the cohort loader's per-patient tuple
    intentionally drops US Core extensions to keep the harness fast. A
    later cut can broaden the loader without changing this surface.
    """
    reference = reference_date or date.today()
    age_brackets = brackets or _default_age_brackets()

    sentinel_report = CohortReport(total_patients=0, bundles_scanned=0)
    patients = _load_cohort(path, sentinel_report, reference)

    age_counter: Counter[tuple[int, int]] = Counter()
    sex_counter: Counter[str] = Counter()
    cond_counter: Counter[str] = Counter()
    # Codes are opaque inside the cohort loader, so the report leans on
    # the cohort_codes_by_type entry for "Condition" to count distinct
    # codes per patient. We can't recover display names from codes alone
    # without re-walking — so we re-walk Bundles lightly for displays.
    # For now, count by code; display recovery is a follow-up.
    for age, sex, condition_codes, _codes_by_type in patients:
        bracket = _bracket_for_age(age, age_brackets)
        if bracket is not None:
            age_counter[bracket] += 1
        if sex:
            sex_counter[sex] += 1
        for code in condition_codes:
            cond_counter[code] += 1

    return CohortDemographics(
        total_patients=len(patients),
        age_brackets=tuple(
            (b, age_counter.get(b, 0)) for b in age_brackets
        ),
        sex=tuple(sorted(sex_counter.items(), key=lambda kv: -kv[1])),
        conditions=tuple(cond_counter.most_common()),
    )


_CSS = """
* { box-sizing: border-box; }
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    max-width: 980px;
    margin: 2rem auto;
    padding: 0 1.5rem;
    color: #1d1d1f;
    line-height: 1.5;
}
header { border-bottom: 1px solid #d2d2d7; padding-bottom: 1rem; margin-bottom: 2rem; }
h1 { margin: 0 0 0.25rem; font-size: 1.75rem; }
h2 { font-size: 1.2rem; margin-top: 2.25rem; border-bottom: 1px solid #ececf0; padding-bottom: 0.35rem; }
.subtitle { color: #6e6e73; font-size: 0.95rem; }
.kv { display: grid; grid-template-columns: max-content 1fr; gap: 0.25rem 1rem; margin: 0.5rem 0 1rem; }
.kv dt { color: #6e6e73; font-size: 0.85rem; }
.kv dd { margin: 0; font-variant-numeric: tabular-nums; }
table { width: 100%; border-collapse: collapse; margin: 0.5rem 0 1rem; font-size: 0.92rem; }
th, td { padding: 0.45rem 0.6rem; text-align: left; }
th { background: #f5f5f7; font-weight: 600; border-bottom: 1px solid #d2d2d7; }
td { border-bottom: 1px solid #ececf0; font-variant-numeric: tabular-nums; }
td.num, th.num { text-align: right; }
.bar { background: #ececf0; border-radius: 3px; height: 8px; width: 140px; display: inline-block; position: relative; vertical-align: middle; }
.bar > span { background: #007aff; border-radius: 3px; height: 100%; display: block; }
.pass { color: #1f7a3a; font-weight: 600; }
.fail { color: #c0392b; font-weight: 600; }
.skip { color: #8a6d00; }
.badge { display: inline-block; padding: 0.1rem 0.5rem; border-radius: 999px; font-size: 0.75rem; font-weight: 600; }
.badge-sourced { background: #e3f2fd; color: #0a558c; }
.badge-verified { background: #e6f4ea; color: #1f7a3a; }
.badge-placeholder { background: #fff4cc; color: #8a6d00; }
footer { margin-top: 3rem; padding-top: 1rem; border-top: 1px solid #ececf0; color: #6e6e73; font-size: 0.8rem; }
"""


def _bar(actual: float, total: float = 1.0) -> str:
    pct = max(0.0, min(100.0, (actual / total) * 100.0 if total else 0.0))
    return f'<span class="bar"><span style="width:{pct:.1f}%"></span></span>'


def _row_count_bar(n: int, total: int) -> str:
    pct = (n / total * 100.0) if total else 0.0
    return f"{_bar(n, total)} {n:,} ({pct:.1f}%)"


def _demographics_section(demo: CohortDemographics) -> str:
    total = demo.total_patients

    age_rows = "\n".join(
        f"<tr><td>{lo}–{hi}</td><td class='num'>{_row_count_bar(n, total)}</td></tr>"
        for (lo, hi), n in demo.age_brackets
    )
    sex_rows = "\n".join(
        f"<tr><td>{html.escape(sex)}</td><td class='num'>{_row_count_bar(n, total)}</td></tr>"
        for sex, n in demo.sex
    ) or "<tr><td colspan='2'><em>no sex recorded</em></td></tr>"

    if demo.conditions:
        cond_rows = "\n".join(
            f"<tr><td>{html.escape(code)}</td>"
            f"<td class='num'>{_row_count_bar(n, total)}</td></tr>"
            for code, n in demo.conditions[:40]
        )
        if len(demo.conditions) > 40:
            cond_rows += (
                f"<tr><td colspan='2'><em>… {len(demo.conditions) - 40} "
                f"more conditions not shown</em></td></tr>"
            )
    else:
        cond_rows = "<tr><td colspan='2'><em>no conditions fired</em></td></tr>"

    return f"""
<h2>Demographics</h2>
<h3>Age brackets</h3>
<table><thead><tr><th>Age</th><th class='num'>Patients</th></tr></thead>
<tbody>{age_rows}</tbody></table>
<h3>Sex</h3>
<table><thead><tr><th>Sex</th><th class='num'>Patients</th></tr></thead>
<tbody>{sex_rows}</tbody></table>
<h2>Conditions</h2>
<table><thead><tr><th>Code</th><th class='num'>Patients</th></tr></thead>
<tbody>{cond_rows}</tbody></table>
"""


def _fidelity_section(
    expectation: Expectation, report: CohortReport
) -> str:
    prov = expectation.source.provenance
    badge_class = {
        "sourced": "badge-sourced",
        "verified": "badge-verified",
        "placeholder": "badge-placeholder",
    }.get(prov, "badge-placeholder")

    if not report.results:
        body = "<p><em>No fidelity metrics evaluated.</em></p>"
    else:
        rows = []
        for r in report.results:
            status = (
                "<span class='pass'>PASS</span>"
                if r.within_tolerance
                else "<span class='fail'>FAIL</span>"
            )
            bracket_label = (
                f"{r.bracket[0]}–{r.bracket[1]}" if r.bracket else "cohort"
            )
            rows.append(
                f"<tr><td>{html.escape(r.metric_id)}</td>"
                f"<td>{bracket_label}</td>"
                f"<td>{html.escape(r.sex or '—')}</td>"
                f"<td class='num'>{r.n:,}</td>"
                f"<td class='num'>{r.actual:.3f}</td>"
                f"<td class='num'>{r.target:.3f}</td>"
                f"<td class='num'>±{r.tolerance:.3f}</td>"
                f"<td>{status}</td></tr>"
            )
        body = (
            "<table><thead><tr>"
            "<th>Metric</th><th>Bracket</th><th>Sex</th>"
            "<th class='num'>N</th><th class='num'>Actual</th>"
            "<th class='num'>Target</th><th class='num'>Tolerance</th>"
            "<th>Status</th></tr></thead><tbody>"
            + "\n".join(rows)
            + "</tbody></table>"
        )

    citations = ""
    if expectation.source.citations:
        items = []
        for c in expectation.source.citations:
            pieces = [html.escape(c.source)]
            if c.version:
                pieces.append(html.escape(c.version))
            if c.url:
                pieces.append(
                    f'<a href="{html.escape(c.url)}">{html.escape(c.url)}</a>'
                )
            items.append("<li>" + " — ".join(pieces) + "</li>")
        citations = "<h3>Citations</h3><ul>" + "\n".join(items) + "</ul>"

    skipped = ""
    if report.skipped:
        items = "\n".join(
            f"<li class='skip'>{html.escape(s)}</li>" for s in report.skipped
        )
        skipped = f"<h3>Skipped</h3><ul>{items}</ul>"

    passed = sum(1 for r in report.results if r.within_tolerance)
    failed = len(report.failing_metrics)
    overall = (
        "<span class='pass'>ALL PASS</span>"
        if report.passed
        else "<span class='fail'>FAILED</span>"
    )

    return f"""
<h2>Fidelity vs. {html.escape(expectation.module)} v{html.escape(expectation.version)}
<span class='badge {badge_class}'>{html.escape(prov)}</span></h2>
<dl class='kv'>
<dt>Result</dt><dd>{overall} — {passed} passed, {failed} failed, {len(report.skipped)} skipped</dd>
</dl>
{body}
{citations}
{skipped}
"""


def build_html_report(
    *,
    cohort_path: Path,
    demographics: CohortDemographics,
    expectation: Expectation | None = None,
    fidelity: CohortReport | None = None,
    generated_at: date | None = None,
) -> str:
    """Render a full HTML document. `expectation`+`fidelity` are paired."""
    when = (generated_at or date.today()).isoformat()
    fidelity_html = (
        _fidelity_section(expectation, fidelity)
        if expectation is not None and fidelity is not None
        else ""
    )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>APEX Atlas cohort report — {html.escape(str(cohort_path))}</title>
<style>{_CSS}</style>
</head>
<body>
<header>
<h1>APEX Atlas cohort report</h1>
<p class="subtitle">Synthetic patient cohort summary — no real patient is depicted.</p>
<dl class="kv">
<dt>Cohort path</dt><dd><code>{html.escape(str(cohort_path))}</code></dd>
<dt>Patients</dt><dd>{demographics.total_patients:,}</dd>
<dt>Generated</dt><dd>{when}</dd>
</dl>
</header>
{_demographics_section(demographics)}
{fidelity_html}
<footer>
Generated by <strong>APEX Atlas</strong>. Synthetic data; no real patient is depicted.
Report is fully self-contained — no network calls, no tracking.
</footer>
</body>
</html>
"""


def write_report(
    cohort_path: Path,
    output_path: Path,
    *,
    expectation: Expectation | None = None,
    min_samples: int = 30,
    reference_date: date | None = None,
) -> tuple[CohortDemographics, CohortReport | None]:
    """High-level driver: collect demographics, optionally run fidelity, write HTML."""
    demographics = collect_demographics(
        cohort_path, reference_date=reference_date
    )
    fidelity: CohortReport | None = None
    if expectation is not None:
        fidelity = evaluate_cohort(
            cohort_path,
            expectation,
            min_samples=min_samples,
            reference_date=reference_date,
        )
    html_doc = build_html_report(
        cohort_path=cohort_path,
        demographics=demographics,
        expectation=expectation,
        fidelity=fidelity,
        generated_at=reference_date,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_doc, encoding="utf-8")
    return demographics, fidelity

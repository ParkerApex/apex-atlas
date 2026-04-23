"""
Parker Atlas command-line interface.

This module is the entry point for the `atlas` command. The `generate`
subcommand is functional for the Milestone 1 vertical slice (FHIR R4
Patient bundles, US Core 6.1); other subcommands remain stubs pending
later milestones. See docs/roadmap.md.
"""

from __future__ import annotations

import json
import random
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.progress import track
from rich.table import Table

from parker_atlas import __version__
from parker_atlas.core.demographics import sample_demographics
from parker_atlas.fhir.bundle import build_bundle, fullurl_for_gpx
from parker_atlas.fhir.condition import build_condition_resource
from parker_atlas.fhir.patient import build_patient_resource
from parker_atlas.gpx import Allocator, Category
from parker_atlas.modules import (
    ModuleError,
    list_bundled_modules,
    load_module,
    run_module,
)
from parker_atlas.validation.cohort import evaluate_cohort
from parker_atlas.validation.expectations import (
    ExpectationError,
    load_bundled_expectation,
)
from parker_atlas.validation.structural import validate_path

app = typer.Typer(
    name="atlas",
    help="Parker Atlas — synthetic FHIR patient population generator.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()
err_console = Console(stderr=True)


class OutputFormat(str, Enum):
    FHIR_R4 = "fhir-r4"
    FHIR_R5 = "fhir-r5"
    NDJSON = "ndjson"
    PARQUET = "parquet"


class Profile(str, Enum):
    US_CORE_6_1 = "us-core-6.1"
    IPS = "ips"
    BASE = "base"


def _not_implemented(command: str, milestone: str) -> None:
    err_console.print(
        f"[yellow]atlas {command}[/yellow] is not yet implemented. "
        f"Ships in [bold]{milestone}[/bold] — see docs/roadmap.md."
    )
    raise typer.Exit(code=2)


def _validate_cohort(
    path: Path, *, module: str | None, min_samples: int, as_of: str | None
) -> None:
    if module is None:
        err_console.print(
            "[red]--cohort requires --module NAME[/red] so the harness knows "
            "which expectation to load. See `atlas modules` for available names."
        )
        raise typer.Exit(code=1)

    try:
        expectation = load_bundled_expectation(module)
    except ExpectationError as exc:
        err_console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    reference_date = date.fromisoformat(as_of) if as_of else None
    report = evaluate_cohort(
        path, expectation, min_samples=min_samples, reference_date=reference_date
    )

    if report.bundles_scanned == 0:
        err_console.print(f"[yellow]No FHIR Bundles found under[/yellow] {path}")
        raise typer.Exit(code=1)

    prov = expectation.source.provenance
    prov_color = {
        "placeholder": "yellow",
        "sourced": "cyan",
        "verified": "green",
    }.get(prov, "white")
    title = (
        f"Cohort fidelity: {expectation.module} v{expectation.version} "
        f"[[{prov_color}]{prov}[/{prov_color}]]"
    )
    table = Table(title=title)
    table.add_column("Metric", style="bold")
    table.add_column("Bracket")
    table.add_column("N", justify="right")
    table.add_column("Actual", justify="right")
    table.add_column("Target", justify="right")
    table.add_column("±", justify="right")
    table.add_column("Status")
    for r in report.results:
        status = "[green]OK[/green]" if r.within_tolerance else "[red]FAIL[/red]"
        table.add_row(
            r.metric_id,
            f"{r.bracket[0]}-{r.bracket[1]}",
            str(r.n),
            f"{r.actual:.3f}",
            f"{r.target:.3f}",
            f"{r.tolerance:.3f}",
            status,
        )
    console.print(table)

    if prov == "placeholder":
        console.print(
            "[yellow]⚠ expectation provenance is 'placeholder'[/yellow] — "
            "targets are curated approximations, not externally cited. "
            "Pass/fail here reflects pipeline correctness, not calibration."
        )
    for cite in expectation.source.citations:
        pieces = [cite.source]
        if cite.version:
            pieces.append(cite.version)
        if cite.url:
            pieces.append(cite.url)
        console.print(f"  cite: {' — '.join(pieces)}")

    for note in report.skipped:
        console.print(f"[yellow]skipped:[/yellow] {note}")
    for p, err in report.parse_errors:
        console.print(f"[red]parse error:[/red] {p}: {err}")

    passed = len([r for r in report.results if r.within_tolerance])
    failed = len(report.failing_metrics)
    console.print(
        f"\n[bold]{report.total_patients}[/bold] patients across "
        f"[bold]{report.bundles_scanned}[/bold] bundles — "
        f"[green]{passed} metric(s) passed[/green], "
        f"[red]{failed} failed[/red], "
        f"[yellow]{len(report.skipped)} skipped[/yellow]"
    )
    raise typer.Exit(code=0 if report.passed else 1)


@app.command()
def generate(
    patients: Annotated[int, typer.Option(help="Number of patients to generate.")] = 1000,
    out: Annotated[Path, typer.Option(help="Output directory.")] = Path("./patients"),
    format: Annotated[OutputFormat, typer.Option(help="Output format.")] = OutputFormat.FHIR_R4,
    module: Annotated[str | None, typer.Option(help="Limit to a single clinical module.")] = None,
    profile: Annotated[Profile, typer.Option(help="FHIR profile to conform to.")] = Profile.US_CORE_6_1,
    seed: Annotated[int | None, typer.Option(help="RNG seed for reproducibility.")] = None,
) -> None:
    """Generate a synthetic FHIR patient population."""
    if patients < 1:
        err_console.print("[red]--patients must be >= 1[/red]")
        raise typer.Exit(code=1)
    if format is not OutputFormat.FHIR_R4:
        err_console.print(
            f"[yellow]--format={format.value}[/yellow] is not yet supported. "
            f"Milestone 1 implements only fhir-r4; ndjson and parquet land in Milestone 5, "
            f"fhir-r5 after."
        )
        raise typer.Exit(code=2)
    if profile is not Profile.US_CORE_6_1:
        err_console.print(
            f"[yellow]--profile={profile.value}[/yellow] is not yet supported. "
            f"Milestone 1 implements only us-core-6.1."
        )
        raise typer.Exit(code=2)
    active_modules = []
    if module is not None:
        try:
            active_modules.append(load_module(module))
        except ModuleError as exc:
            err_console.print(f"[red]{exc}[/red]")
            raise typer.Exit(code=1) from exc

    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    allocator = Allocator(Category.SYNTHETIC)

    today = date.today()

    description = f"Generating {patients} patient{'s' if patients != 1 else ''}"
    for _ in track(range(patients), description=description, console=console):
        demo = sample_demographics(rng, today=today)
        gpx = allocator.allocate()
        patient = build_patient_resource(gpx, demo)
        patient_url = fullurl_for_gpx(gpx)

        extras: list[dict] = []
        age_years = (today - demo.birth_date).days // 365
        for mod in active_modules:
            for dx in run_module(mod, age_years=age_years, sex=demo.gender.value, rng=rng):
                extras.append(
                    build_condition_resource(
                        gpx=gpx,
                        patient_fullurl=patient_url,
                        condition_spec_id=dx.condition.id,
                        code=dx.condition.code,
                    )
                )

        bundle = build_bundle(gpx, patient, extras)
        (out / f"{gpx}.json").write_text(json.dumps(bundle, indent=2))

    console.print(
        f"[green]✓[/green] Wrote {patients} patient bundle"
        f"{'s' if patients != 1 else ''} to [bold]{out}[/bold]"
    )


@app.command()
def validate(
    path: Annotated[Path, typer.Argument(help="Path to FHIR resources to validate.")],
    profile: Annotated[Profile, typer.Option(help="FHIR profile to validate against.")] = Profile.US_CORE_6_1,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Show per-file errors and warnings.")] = False,
    strict: Annotated[bool, typer.Option("--strict", help="Treat warnings as errors.")] = False,
    cohort: Annotated[bool, typer.Option("--cohort", help="Run cohort fidelity harness instead of per-file structural.")] = False,
    module: Annotated[str | None, typer.Option(help="Module whose bundled expectation to run under --cohort.")] = None,
    min_samples: Annotated[int, typer.Option(help="Minimum bracket N under --cohort; smaller brackets are skipped.")] = 30,
    as_of: Annotated[str | None, typer.Option(help="ISO date used as the reference for age computation under --cohort.")] = None,
) -> None:
    """Validate generated FHIR resources.

    Default mode is structural: schema validation via fhir.resources plus US
    Core 6.1 Patient/Condition minimum elements, per file. This is not a full
    profile conformance check — that requires an external FHIR validator.

    `--cohort --module NAME` runs the cohort fidelity harness instead: load the
    bundled expectation for `NAME`, compute aggregate metrics over the cohort,
    and compare each target within tolerance.
    """
    if not path.exists():
        err_console.print(f"[red]path does not exist:[/red] {path}")
        raise typer.Exit(code=1)
    if profile is not Profile.US_CORE_6_1:
        err_console.print(
            f"[yellow]--profile={profile.value}[/yellow] is not yet supported. "
            "Milestone 1 implements only us-core-6.1."
        )
        raise typer.Exit(code=2)

    if cohort:
        _validate_cohort(path, module=module, min_samples=min_samples, as_of=as_of)
        return

    summary = validate_path(path)

    if summary.total == 0:
        err_console.print(f"[yellow]No JSON files found under[/yellow] {path}")
        raise typer.Exit(code=1)

    if verbose:
        for f in summary.files:
            status = "[green]OK[/green]" if f.ok else "[red]FAIL[/red]"
            console.print(f"{status} {f.path}")
            for err in f.errors:
                console.print(f"  [red]error:[/red] {err}")
            for warn in f.warnings:
                console.print(f"  [yellow]warning:[/yellow] {warn}")

    console.print(
        f"Validated [bold]{summary.total}[/bold] file(s): "
        f"[green]{summary.passed} passed[/green], "
        f"[red]{summary.failed} failed[/red], "
        f"[yellow]{summary.warnings} warning(s)[/yellow]"
    )

    failed = summary.failed > 0 or (strict and summary.warnings > 0)
    raise typer.Exit(code=1 if failed else 0)


@app.command()
def modules(
    list_: Annotated[bool, typer.Option("--list", help="List available modules.")] = False,
    show: Annotated[str | None, typer.Option(help="Show details for a module by name.")] = None,
) -> None:
    """Inspect the clinical module library."""
    if show:
        try:
            mod = load_module(show)
        except ModuleError as exc:
            err_console.print(f"[red]{exc}[/red]")
            raise typer.Exit(code=1) from exc
        console.print(f"[bold]{mod.name}[/bold] v{mod.version}")
        if mod.description:
            console.print(mod.description.strip())
        if mod.cites:
            console.print("\n[bold]Cites[/bold]")
            for c in mod.cites:
                console.print(f"  - {c.source}: {c.url}")
                if c.summary:
                    console.print(f"    {c.summary.strip()}")
        console.print("\n[bold]Conditions[/bold]")
        for cond in mod.conditions:
            console.print(f"  - {cond.id} ({cond.code.system} {cond.code.code}: {cond.code.display})")
        return

    # Default behavior (including --list): show the catalog.
    names = list_bundled_modules()
    if not names:
        console.print("No bundled modules.")
        return
    table = Table(title="Bundled Parker Atlas modules")
    table.add_column("Name", style="bold")
    table.add_column("Version")
    table.add_column("Conditions")
    for name in names:
        try:
            mod = load_module(name)
            table.add_row(mod.name, mod.version, str(len(mod.conditions)))
        except ModuleError as exc:  # pragma: no cover — defensive
            table.add_row(name, "[red]load error[/red]", str(exc))
    console.print(table)
    if not list_:
        console.print("\nUse [bold]atlas modules --show NAME[/bold] for details.")


@app.command()
def version() -> None:
    """Print the installed Parker Atlas version."""
    console.print(f"parker-atlas {__version__}")


@app.command()
def status() -> None:
    """Print implementation status of each subsystem."""
    table = Table(title="Parker Atlas — implementation status", show_lines=False)
    table.add_column("Component", style="bold")
    table.add_column("Status")
    table.add_column("Milestone")

    rows = [
        ("GPX identifier",        "[green]implemented[/green]",    "M0"),
        ("CLI scaffolding",       "[green]implemented[/green]",    "M0"),
        ("Demographic sampling",  "[yellow]placeholder[/yellow]",  "M1"),
        ("FHIR Patient builder",  "[green]implemented[/green]",    "M1"),
        ("FHIR Condition builder","[green]implemented[/green]",    "M1"),
        ("atlas generate",        "[green]implemented[/green]",    "M1"),
        ("atlas validate",        "[green]structural[/green]",     "M1"),
        ("atlas validate --cohort","[green]first cut[/green]",      "M2"),
        ("Module runtime",        "[yellow]probability[/yellow]",  "M2"),
        ("Module library",        "[yellow]1 module[/yellow]",     "M2"),
        ("Fidelity harness",      "[yellow]1 module[/yellow]",     "M2"),
        ("LLM authoring",         "[dim]not started[/dim]",        "M3"),
        ("Clinical notes",        "[dim]not started[/dim]",        "M4"),
    ]
    for row in rows:
        table.add_row(*row)
    console.print(table)


if __name__ == "__main__":
    app()

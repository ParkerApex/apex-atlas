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
from enum import Enum
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.progress import track
from rich.table import Table

from parker_atlas import __version__
from parker_atlas.core.demographics import sample_demographics
from parker_atlas.fhir.bundle import patient_bundle
from parker_atlas.fhir.patient import build_patient_resource
from parker_atlas.gpx import Allocator, Category
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
    if module is not None:
        err_console.print(
            "[yellow]--module[/yellow] is not yet supported. "
            "Clinical modules arrive in Milestone 2."
        )
        raise typer.Exit(code=2)

    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    allocator = Allocator(Category.SYNTHETIC)

    description = f"Generating {patients} patient{'s' if patients != 1 else ''}"
    for _ in track(range(patients), description=description, console=console):
        demo = sample_demographics(rng)
        gpx = allocator.allocate()
        patient = build_patient_resource(gpx, demo)
        bundle = patient_bundle(gpx, patient)
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
) -> None:
    """Validate generated FHIR resources structurally.

    Performs schema validation via fhir.resources and checks US Core 6.1
    Patient minimum elements. This is not a full profile conformance check
    — that requires an external FHIR validator.
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
    _not_implemented("modules", "Milestone 2")


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
        ("CLI scaffolding",       "[yellow]stub[/yellow]",         "M0"),
        ("Simulation core",       "[dim]not started[/dim]",        "M1"),
        ("FHIR builders",         "[dim]not started[/dim]",        "M1"),
        ("Module runtime",        "[dim]not started[/dim]",        "M2"),
        ("Module library",        "[dim]not started[/dim]",        "M2"),
        ("Statistical validation","[dim]not started[/dim]",        "M2"),
        ("LLM authoring",         "[dim]not started[/dim]",        "M3"),
        ("Clinical notes",        "[dim]not started[/dim]",        "M4"),
    ]
    for row in rows:
        table.add_row(*row)
    console.print(table)


if __name__ == "__main__":
    app()

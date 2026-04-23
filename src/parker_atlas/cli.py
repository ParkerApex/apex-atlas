"""
Parker Atlas command-line interface.

This module is the entry point for the `atlas` command. The subcommands
are scaffolded as stubs; implementations arrive over the milestones
described in docs/roadmap.md.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from parker_atlas import __version__

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
    _not_implemented("generate", "Milestone 1")


@app.command()
def validate(
    path: Annotated[Path, typer.Argument(help="Path to FHIR resources to validate.")],
    profile: Annotated[Profile, typer.Option(help="FHIR profile to validate against.")] = Profile.US_CORE_6_1,
) -> None:
    """Validate FHIR resources against a profile."""
    _not_implemented("validate", "Milestone 1")


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

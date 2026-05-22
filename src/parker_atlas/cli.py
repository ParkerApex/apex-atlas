"""
APEX Atlas command-line interface.

This module is the entry point for the `atlas` command. The `generate`
subcommand is functional for the Milestone 1 vertical slice (FHIR R4
Patient bundles, US Core 6.1); other subcommands remain stubs pending
later milestones. See docs/roadmap.md.
"""

from __future__ import annotations

import json
import random
from collections import Counter
from datetime import date, timedelta
from enum import Enum
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.progress import track
from rich.table import Table

from parker_atlas import __version__
from parker_atlas.core.demographics import race_display, sample_demographics
from parker_atlas.core.payer import sample_payer
from parker_atlas.fhir.allergy_intolerance import build_allergy_intolerance_resource
from parker_atlas.fhir.bundle import build_bundle, fullurl_for_gpx, fullurl_for_resource
from parker_atlas.fhir.claim import (
    build_claim_resource,
    build_explanation_of_benefit_resource,
)
from parker_atlas.fhir.condition import build_condition_resource
from parker_atlas.fhir.coverage import build_coverage_resource
from parker_atlas.fhir.diagnostic_report import build_diagnostic_report_resource
from parker_atlas.fhir.insurance_plan import build_insurance_plan_resource
from parker_atlas.fhir.organization import build_payer_organization_resource
from parker_atlas.fhir.document_reference import build_document_reference_resource
from parker_atlas.core.provider import sample_care_team
from parker_atlas.fhir.encounter import build_encounter_resource
from parker_atlas.fhir.location import build_location_resource
from parker_atlas.fhir.organization import build_facility_organization_resource
from parker_atlas.fhir.practitioner import build_practitioner_resource
from parker_atlas.fhir.practitioner_role import build_practitioner_role_resource
from parker_atlas.fhir.immunization import build_immunization_resource
from parker_atlas.fhir.medication_request import build_medication_request_resource
from parker_atlas.fhir.mortality import build_cause_of_death_observation_resource
from parker_atlas.fhir.observation import (
    ObservationComponent,
    Quantity,
    build_observation_resource,
)
from parker_atlas.fhir.patient import build_patient_resource
from parker_atlas.fhir.procedure import build_procedure_resource
from parker_atlas.notes import (
    NoteContext,
    NoteStrategy,
    build_progress_note_text,
)
from parker_atlas.gpx import Allocator, Category
from parker_atlas.modules import (
    ModuleError,
    SampledAllergyIntolerance,
    SampledDiagnosticReport,
    SampledEncounter,
    SampledImmunization,
    SampledMedicationRequest,
    SampledObservation,
    SampledProcedure,
    apply_cross_module_progressions,
    list_bundled_modules,
    load_module,
    run_module,
)
from parker_atlas.validation.cohort import evaluate_cohort
from parker_atlas.validation.expectations import (
    ExpectationError,
    load_bundled_expectation,
)
from parker_atlas.validation.report import write_report
from parker_atlas.validation.structural import validate_path

app = typer.Typer(
    name="atlas",
    help="APEX Atlas — synthetic FHIR patient population generator.",
    no_args_is_help=True,
    add_completion=False,
)

ingest_app = typer.Typer(
    name="ingest",
    help="Ingest external data sources into APEX Atlas (prevalence, demographics, …).",
    no_args_is_help=True,
)
app.add_typer(ingest_app)

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


def _build_provider_resources(
    *,
    gpx,
    care_team,
    bundle_emitted_ids: set[str],
) -> tuple[list[dict], str, str, str]:
    """Build (or reuse) the Practitioner/facility-Org/Location/Role for a care team.

    Returns (new_resources, practitioner_url, location_url, facility_org_url).
    Resources whose deterministic id is already in `bundle_emitted_ids`
    are reused (URL returned but resource not duplicated). Caller is
    responsible for adding new resources to the bundle and updating the
    per-bundle dedup set.
    """
    new_resources: list[dict] = []

    prac = care_team.practitioner
    loc = care_team.location

    facility_org = build_facility_organization_resource(
        npi=loc.facility_npi,
        name=loc.facility_name,
        org_role=loc.facility_role,  # type: ignore[arg-type]
    )
    facility_org_url = fullurl_for_resource(gpx, facility_org)
    if facility_org["id"] not in bundle_emitted_ids:
        new_resources.append(facility_org)
        bundle_emitted_ids.add(facility_org["id"])

    practitioner = build_practitioner_resource(
        npi=prac.npi, family=prac.family, given=prac.given, prefix=prac.prefix
    )
    practitioner_url = fullurl_for_resource(gpx, practitioner)
    if practitioner["id"] not in bundle_emitted_ids:
        new_resources.append(practitioner)
        bundle_emitted_ids.add(practitioner["id"])

    location = build_location_resource(
        facility_npi=loc.facility_npi,
        location_name=loc.location_name,
        location_type_code=loc.location_type_code,
        location_type_display=loc.location_type_display,
        line=loc.line,
        city=loc.city,
        state=loc.state,
        postal_code=loc.postal_code,
        facility_organization_fullurl=facility_org_url,
    )
    location_url = fullurl_for_resource(gpx, location)
    if location["id"] not in bundle_emitted_ids:
        new_resources.append(location)
        bundle_emitted_ids.add(location["id"])

    role = build_practitioner_role_resource(
        practitioner_npi=prac.npi,
        facility_npi=loc.facility_npi,
        taxonomy_code=prac.taxonomy_code,
        taxonomy_display=prac.taxonomy_display,
        practitioner_fullurl=practitioner_url,
        facility_organization_fullurl=facility_org_url,
    )
    if role["id"] not in bundle_emitted_ids:
        new_resources.append(role)
        bundle_emitted_ids.add(role["id"])

    return new_resources, practitioner_url, location_url, facility_org_url


def _build_emitted_resources(
    *,
    gpx,
    patient_url: str,
    diagnosis,
    provider_rng=None,
    bundle_emitted_ids: set[str] | None = None,
) -> list[dict]:
    """Convert a Diagnosis's sampled resources into FHIR dicts.

    Linking rules:
    - If a non-Encounter resource declares an explicit `link_to`, it
      references the Encounter with that spec_id. (The parser already
      validated the spec_id exists.)
    - Otherwise, if exactly one Encounter was emitted *and* the
      resource's `when` matches the Encounter's `when`, link to it
      (preserves single-encounter backward compatibility).
    - Otherwise, no Encounter link.
    """
    built: list[dict] = []

    # First pass: build all Encounters and collect their fullUrls keyed
    # by spec_id so other emits can resolve link_to.
    encounter_urls: dict[str, str] = {}
    observation_urls: dict[str, str] = {}
    sampled_encounters: list = []
    for sr in diagnosis.sampled_resources:
        if isinstance(sr, SampledEncounter):
            practitioner_url: str | None = None
            location_url: str | None = None
            service_provider_url: str | None = None
            if provider_rng is not None and bundle_emitted_ids is not None:
                care_team = sample_care_team(
                    provider_rng, class_code=sr.encounter_class
                )
                provider_res, practitioner_url, location_url, service_provider_url = (
                    _build_provider_resources(
                        gpx=gpx,
                        care_team=care_team,
                        bundle_emitted_ids=bundle_emitted_ids,
                    )
                )
                built.extend(provider_res)
            enc = build_encounter_resource(
                gpx=gpx,
                patient_fullurl=patient_url,
                encounter_spec_id=sr.spec_id,
                class_code=sr.encounter_class,
                type_code=sr.type_code,
                period_start=sr.effective_date,
                period_end=sr.effective_date,
                reason_code=sr.reason_code,
                practitioner_fullurl=practitioner_url,
                location_fullurl=location_url,
                service_provider_fullurl=service_provider_url,
            )
            built.append(enc)
            encounter_urls[sr.spec_id] = fullurl_for_resource(gpx, enc)
            sampled_encounters.append(sr)

    # Default-link target: only meaningful when there's exactly one
    # Encounter (otherwise auto-linking would be ambiguous).
    default_url: str | None = None
    default_when: str | None = None
    if len(sampled_encounters) == 1:
        only = sampled_encounters[0]
        default_url = encounter_urls[only.spec_id]
        default_when = only.when

    def _resolve_link(sr) -> str | None:
        if sr.link_to is not None:
            return encounter_urls.get(sr.link_to)
        if default_url is not None and sr.when == default_when:
            return default_url
        return None

    for sr in diagnosis.sampled_resources:
        if isinstance(sr, SampledEncounter):
            continue  # already handled
        if isinstance(sr, SampledDiagnosticReport):
            continue  # built after Observations so result refs resolve
        link = _resolve_link(sr)
        if isinstance(sr, SampledObservation):
            if sr.components:
                components = tuple(
                    ObservationComponent(
                        code=c.code,
                        value=Quantity(value=c.value, unit=c.unit, code=c.unit_code),
                    )
                    for c in sr.components
                )
                obs = build_observation_resource(
                    gpx=gpx,
                    patient_fullurl=patient_url,
                    observation_spec_id=sr.spec_id,
                    category=sr.category,
                    code=sr.code,
                    effective=sr.effective_date,
                    components=components,
                )
            else:
                assert sr.value is not None and sr.unit is not None
                obs = build_observation_resource(
                    gpx=gpx,
                    patient_fullurl=patient_url,
                    observation_spec_id=sr.spec_id,
                    category=sr.category,
                    code=sr.code,
                    effective=sr.effective_date,
                    value=Quantity(
                        value=sr.value,
                        unit=sr.unit,
                        code=sr.unit_code or sr.unit,
                    ),
                )
            if link is not None:
                obs["encounter"] = {"reference": link}
            built.append(obs)
            observation_urls[sr.spec_id] = fullurl_for_resource(gpx, obs)
        elif isinstance(sr, SampledMedicationRequest):
            med = build_medication_request_resource(
                gpx=gpx,
                patient_fullurl=patient_url,
                medication_spec_id=sr.spec_id,
                medication_code=sr.medication_code,
                authored_on=sr.effective_date,
                reason_code=sr.reason_code,
                encounter_fullurl=link,
            )
            built.append(med)
        elif isinstance(sr, SampledProcedure):
            proc = build_procedure_resource(
                gpx=gpx,
                patient_fullurl=patient_url,
                procedure_spec_id=sr.spec_id,
                code=sr.code,
                performed_date=sr.effective_date,
                reason_code=sr.reason_code,
                encounter_fullurl=link,
            )
            built.append(proc)
        elif isinstance(sr, SampledAllergyIntolerance):
            allergy = build_allergy_intolerance_resource(
                gpx=gpx,
                patient_fullurl=patient_url,
                allergy_spec_id=sr.spec_id,
                code=sr.code,
                recorded_date=sr.effective_date,
                category=sr.category,
                criticality=sr.criticality,
                reaction_manifestation=sr.reaction_manifestation,
            )
            built.append(allergy)
        elif isinstance(sr, SampledImmunization):
            imm = build_immunization_resource(
                gpx=gpx,
                patient_fullurl=patient_url,
                immunization_spec_id=sr.spec_id,
                vaccine_code=sr.vaccine_code,
                occurrence=sr.effective_date,
                encounter_fullurl=link,
            )
            built.append(imm)

    for sr in diagnosis.sampled_resources:
        if not isinstance(sr, SampledDiagnosticReport):
            continue
        link = _resolve_link(sr)
        result_refs = tuple(
            observation_urls[sid]
            for sid in sr.result_spec_ids
            if sid in observation_urls
        )
        if not result_refs:
            continue
        report = build_diagnostic_report_resource(
            gpx=gpx,
            patient_fullurl=patient_url,
            report_spec_id=sr.spec_id,
            code=sr.code,
            effective=sr.effective_date,
            result_fullurls=result_refs,
            conclusion=sr.conclusion,
            encounter_fullurl=link,
        )
        built.append(report)

    return built


def _summary_brackets() -> tuple[tuple[int, int], ...]:
    """Age brackets used by the generate summary. Matches references/tables/age_sex.csv."""
    from parker_atlas.references import load_age_sex

    return tuple(sorted({(b.age_low, b.age_high) for b in load_age_sex()}))


def _bracket_for_age(
    age: int, brackets: tuple[tuple[int, int], ...]
) -> tuple[int, int] | None:
    for lo, hi in brackets:
        if lo <= age <= hi:
            return (lo, hi)
    return None


def _print_generate_summary(
    *,
    patients: int,
    age_counter: Counter[tuple[int, int]],
    sex_counter: Counter[str],
    race_counter: Counter[str],
    condition_counter: Counter[str],
    summary_brackets: tuple[tuple[int, int], ...],
    modules: list[str],
) -> None:
    console.print()
    age_tbl = Table(title="Age brackets", show_edge=False)
    age_tbl.add_column("Bracket", style="bold")
    age_tbl.add_column("N", justify="right")
    age_tbl.add_column("%", justify="right")
    for bracket in summary_brackets:
        n = age_counter.get(bracket, 0)
        pct = 100.0 * n / patients if patients else 0.0
        age_tbl.add_row(f"{bracket[0]}-{bracket[1]}", str(n), f"{pct:.1f}%")
    console.print(age_tbl)

    sex_tbl = Table(title="Sex", show_edge=False)
    sex_tbl.add_column("Sex", style="bold")
    sex_tbl.add_column("N", justify="right")
    sex_tbl.add_column("%", justify="right")
    for sex in ("female", "male"):
        n = sex_counter.get(sex, 0)
        pct = 100.0 * n / patients if patients else 0.0
        sex_tbl.add_row(sex, str(n), f"{pct:.1f}%")
    console.print(sex_tbl)

    race_tbl = Table(title="Race", show_edge=False)
    race_tbl.add_column("Race", style="bold")
    race_tbl.add_column("N", justify="right")
    race_tbl.add_column("%", justify="right")
    for label, n in race_counter.most_common():
        pct = 100.0 * n / patients if patients else 0.0
        race_tbl.add_row(label, str(n), f"{pct:.1f}%")
    console.print(race_tbl)

    if modules:
        cond_tbl = Table(
            title=f"Conditions (modules: {', '.join(modules)})", show_edge=False
        )
        cond_tbl.add_column("Condition", style="bold")
        cond_tbl.add_column("Patients", justify="right")
        cond_tbl.add_column("%", justify="right")
        if not condition_counter:
            cond_tbl.add_row("(none fired)", "0", "0.0%")
        else:
            for label, n in condition_counter.most_common():
                pct = 100.0 * n / patients if patients else 0.0
                cond_tbl.add_row(label, str(n), f"{pct:.1f}%")
        console.print(cond_tbl)


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
    table.add_column("Sex")
    table.add_column("N", justify="right")
    table.add_column("Actual", justify="right")
    table.add_column("Target", justify="right")
    table.add_column("±", justify="right")
    table.add_column("Status")
    for r in report.results:
        status = "[green]OK[/green]" if r.within_tolerance else "[red]FAIL[/red]"
        bracket_label = (
            f"{r.bracket[0]}-{r.bracket[1]}" if r.bracket else "cohort"
        )
        table.add_row(
            r.metric_id,
            bracket_label,
            r.sex or "—",
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
    module: Annotated[str | None, typer.Option(help="Module(s) to run, comma-separated for multiple (e.g. hypertension,complications).")] = None,
    profile: Annotated[Profile, typer.Option(help="FHIR profile to conform to.")] = Profile.US_CORE_6_1,
    seed: Annotated[int | None, typer.Option(help="RNG seed for reproducibility.")] = None,
    summary: Annotated[bool, typer.Option("--summary", help="Print cohort demographics and condition summary after generation.")] = False,
    with_notes: Annotated[bool, typer.Option("--with-notes", help="Emit one DocumentReference (progress note) per fired condition.")] = False,
    notes_strategy: Annotated[NoteStrategy, typer.Option("--notes-strategy", help="Strategy for --with-notes: 'template' (deterministic, no API) or 'llm' (Claude-authored narrative; requires ANTHROPIC_API_KEY).")] = NoteStrategy.TEMPLATE,
    llm_model: Annotated[str | None, typer.Option("--llm-model", help="Claude model id for --notes-strategy=llm (e.g. claude-haiku-4-5-20251001, claude-sonnet-4-6, claude-opus-4-7). Defaults to Haiku 4.5.")] = None,
    with_coverage: Annotated[bool, typer.Option("--with-coverage", help="Sample a payer per patient and emit Coverage + payer Organization + InsurancePlan resources.")] = False,
    with_providers: Annotated[bool, typer.Option("--with-providers", help="Sample a Practitioner + facility Organization + Location per encounter; attach as Encounter.participant / .location / .serviceProvider.")] = False,
    with_claims: Annotated[bool, typer.Option("--with-claims", help="Emit one Claim + ExplanationOfBenefit per Encounter. Requires --with-coverage; uninsured patients receive no claims.")] = False,
) -> None:
    """Generate a synthetic FHIR patient population."""
    if patients < 1:
        err_console.print("[red]--patients must be >= 1[/red]")
        raise typer.Exit(code=1)
    if format not in (OutputFormat.FHIR_R4, OutputFormat.NDJSON, OutputFormat.PARQUET):
        err_console.print(
            f"[yellow]--format={format.value}[/yellow] is not yet supported. "
            f"Currently implemented: fhir-r4 (one Bundle per patient), "
            f"ndjson (one file per resourceType, FHIR Bulk Data style), and "
            f"parquet (columnar, one file per resourceType)."
        )
        raise typer.Exit(code=2)
    if format is OutputFormat.PARQUET:
        try:
            import pyarrow  # noqa: F401
        except ImportError as exc:
            err_console.print(
                "[red]parquet output requires pyarrow.[/red] "
                'Install with: pip install -e ".[data]"'
            )
            raise typer.Exit(code=1) from exc
    if profile is not Profile.US_CORE_6_1:
        err_console.print(
            f"[yellow]--profile={profile.value}[/yellow] is not yet supported. "
            f"Milestone 1 implements only us-core-6.1."
        )
        raise typer.Exit(code=2)
    if with_claims and not with_coverage:
        err_console.print("[red]--with-claims requires --with-coverage[/red]")
        raise typer.Exit(code=1)
    active_modules = []
    if module is not None:
        for name in [m.strip() for m in module.split(",") if m.strip()]:
            try:
                active_modules.append(load_module(name))
            except ModuleError as exc:
                err_console.print(f"[red]{exc}[/red]")
                raise typer.Exit(code=1) from exc

    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    allocator = Allocator(Category.SYNTHETIC)

    today = date.today()

    # Summary counters are populated regardless; only rendered if --summary.
    age_counter: Counter[tuple[int, int]] = Counter()
    sex_counter: Counter[str] = Counter()
    race_counter: Counter[str] = Counter()
    condition_counter: Counter[str] = Counter()
    summary_brackets = _summary_brackets()

    # NDJSON writer state — one open file per resourceType, lazily opened
    # on first encounter, closed in the finally block below. Matches the
    # FHIR Bulk Data Access ($export) convention.
    ndjson_files: dict[str, Any] = {}

    # Payer Organizations + InsurancePlans use payer-scoped (not GPX-scoped)
    # deterministic ids so they merge on ingest. For NDJSON/Parquet output we
    # also dedupe writes by payer_id, since those formats are one-row-per-
    # resource (unlike Bundles, which must self-contain). Bundles always
    # include the payer Org + Plan so cross-Bundle refs resolve.
    emitted_payer_ids_ndjson: set[str] = set()

    # Provider-side resources (Practitioner, PractitionerRole, Location,
    # facility Organization) are likewise deterministic-id'd and merge
    # cleanly on ingest. NDJSON/Parquet dedupe by resource id (one row
    # per provider/location/role across the whole run); Bundles always
    # self-contain the rows used by their Encounters.
    emitted_provider_ids_ndjson: set[str] = set()

    # Parquet writer state — accumulate rows per resourceType in memory,
    # flushed to one file per resourceType at the end. Schema is uniform:
    # id, subject_reference (nullable; null for Patient), raw_json. The
    # raw_json column preserves the full FHIR resource for round-tripping;
    # the typed columns make common filters (by patient, by id) cheap.
    parquet_rows: dict[str, list[dict[str, Any]]] = {}

    description = f"Generating {patients} patient{'s' if patients != 1 else ''}"
    try:
        for _ in track(range(patients), description=description, console=console):
            demo = sample_demographics(rng, today=today)
            gpx = allocator.allocate()
            patient = build_patient_resource(gpx, demo)
            patient_url = fullurl_for_gpx(gpx)

            extras: list[dict] = []
            age_years = (today - demo.birth_date).days // 365

            # Per-Bundle set tracking provider-side resource ids already
            # emitted into this patient's extras. Lets multiple Encounters
            # in the same Bundle share the same Practitioner/Location
            # without duplicate entries.
            bundle_provider_ids: set[str] = set()
            provider_rng = rng if with_providers else None

            # Payer assignment + Coverage emission. Org + Plan have stable
            # (payer-scoped, not patient-scoped) ids so they merge on ingest.
            # Every Bundle that uses the payer must self-contain the Org +
            # Plan so cross-Bundle references resolve under FHIR transaction
            # semantics; NDJSON/Parquet dedup is enforced by `emitted_payer_ids`.
            patient_payer_id: str | None = None
            patient_payer_type: str | None = None
            patient_coverage_url: str | None = None
            patient_payer_org_url: str | None = None
            if with_coverage:
                payer = sample_payer(rng, age_years=age_years)
                if payer is not None:
                    patient_payer_id = payer.payer_id
                    patient_payer_type = payer.payer_type
                    payer_org = build_payer_organization_resource(
                        payer_id=payer.payer_id, name=payer.name
                    )
                    payer_org_url = fullurl_for_resource(gpx, payer_org)
                    patient_payer_org_url = payer_org_url
                    plan = build_insurance_plan_resource(
                        payer_id=payer.payer_id,
                        payer_type=payer.payer_type,
                        plan_name=payer.name,
                        payer_organization_fullurl=payer_org_url,
                    )
                    plan_url = fullurl_for_resource(gpx, plan)
                    coverage = build_coverage_resource(
                        gpx=gpx,
                        patient_fullurl=patient_url,
                        payer_id=payer.payer_id,
                        payer_type=payer.payer_type,
                        payer_organization_fullurl=payer_org_url,
                        insurance_plan_fullurl=plan_url,
                    )
                    patient_coverage_url = fullurl_for_resource(gpx, coverage)
                    extras.append(payer_org)
                    extras.append(plan)
                    extras.append(coverage)
            # First pass: run every active module to collect this patient's
            # full set of fired diagnoses, in the order modules were run.
            # Cross-module `requires` (e.g. hypertension:essential_hypertension)
            # is satisfied against the running `patient_fired` set; same-module
            # `requires` uses a separate per-run set inside run_module.
            diagnoses_by_module: dict[str, list] = {}
            module_order: list[str] = []
            patient_fired: set[str] = set()
            for mod in active_modules:
                diagnoses = run_module(
                    mod,
                    age_years=age_years,
                    sex=demo.gender.value,
                    rng=rng,
                    today=today,
                    external_fired=patient_fired,
                )
                module_order.append(mod.name)
                diagnoses_by_module[mod.name] = list(diagnoses)
                for dx in diagnoses:
                    patient_fired.add(f"{mod.name}:{dx.condition.id}")

            # Cross-module progressions: a fired condition in module A may
            # carry a `to: <module B>:<cond>` progression. After every
            # module's prevalence + same-module pass is complete, we walk
            # the full diagnosis set and fire cross-module targets that
            # pass the time + Bernoulli gates.
            modules_by_name = {m.name: m for m in active_modules}
            diagnoses_by_module = apply_cross_module_progressions(
                diagnoses_by_module,
                modules_by_name=modules_by_name,
                rng=rng,
                today=today,
            )

            all_dx_in_order: list[tuple[str, Any]] = [
                (mod_name, dx)
                for mod_name in module_order
                for dx in diagnoses_by_module.get(mod_name, [])
            ]

            # Second pass: build FHIR resources for each diagnosis. Notes (if
            # enabled) get the full problem list via NoteContext.diagnoses,
            # with the focused dx surfaced as primary_diagnosis.
            all_diagnoses = tuple(dx for _, dx in all_dx_in_order)
            mortality_candidates: list[tuple[date, str, Any]] = []
            for mod_name, dx in all_dx_in_order:
                mortality = dx.condition.mortality
                if mortality is None or dx.onset_date is None:
                    continue
                death_date = dx.onset_date + timedelta(
                    days=mortality.after_years * 365
                )
                if death_date > today:
                    continue
                if rng.random() < mortality.probability:
                    mortality_candidates.append((death_date, mod_name, dx))

            death_event: tuple[date, str, Any] | None = None
            if mortality_candidates:
                death_event = sorted(
                    mortality_candidates,
                    key=lambda item: (item[0], item[1], item[2].condition.id),
                )[0]
                patient["deceasedDateTime"] = death_event[0].isoformat()

            for mod_name, dx in all_dx_in_order:
                extras.append(
                    build_condition_resource(
                        gpx=gpx,
                        patient_fullurl=patient_url,
                        condition_spec_id=dx.condition.id,
                        code=dx.condition.code,
                        onset_date=dx.onset_date,
                    )
                )
                condition_counter[dx.condition.code.display] += 1
                dx_emits = _build_emitted_resources(
                    gpx=gpx,
                    patient_url=patient_url,
                    diagnosis=dx,
                    provider_rng=provider_rng,
                    bundle_emitted_ids=bundle_provider_ids,
                )
                extras.extend(dx_emits)
                if with_notes:
                    # Anchor the note to the first Encounter emitted for
                    # this diagnosis (typically the diagnosis or follow-up
                    # visit). If the module emits no Encounter, the note
                    # is patient-scoped only.
                    encounter_url: str | None = None
                    for r in dx_emits:
                        if r["resourceType"] == "Encounter":
                            encounter_url = fullurl_for_resource(gpx, r)
                            break
                    ctx = NoteContext(
                        patient_display_name=(
                            f"{demo.family_name}, {demo.given_name}"
                        ),
                        age_years=age_years,
                        sex=demo.gender.value,
                        today=today,
                        diagnoses=all_diagnoses,
                        primary_diagnosis=dx,
                    )
                    if notes_strategy is NoteStrategy.LLM:
                        from parker_atlas.notes import (
                            LLMNotesUnavailable,
                            render_llm_note,
                        )

                        try:
                            llm_kwargs = {"model": llm_model} if llm_model else {}
                            note_text = render_llm_note(ctx, **llm_kwargs).text
                        except LLMNotesUnavailable as exc:
                            err_console.print(
                                f"[red]LLM note authoring failed:[/red] {exc}"
                            )
                            raise typer.Exit(code=1) from exc
                    else:
                        note_text = build_progress_note_text(ctx)
                    extras.append(
                        build_document_reference_resource(
                            gpx=gpx,
                            patient_fullurl=patient_url,
                            doc_spec_id=f"progress_{mod_name}_{dx.condition.id}",
                            note_text=note_text,
                            authored_on=today,
                            encounter_fullurl=encounter_url,
                        )
                    )

            if death_event is not None:
                death_date, mod_name, dx = death_event
                cause_code = (
                    dx.condition.mortality.cause_code
                    if dx.condition.mortality
                    else None
                )
                cause_code = cause_code or dx.condition.code
                terminal_spec_id = f"terminal_{mod_name}_{dx.condition.id}"
                extras.append(
                    build_condition_resource(
                        gpx=gpx,
                        patient_fullurl=patient_url,
                        condition_spec_id=terminal_spec_id,
                        code=cause_code,
                        onset_date=death_date,
                    )
                )
                extras.append(
                    build_cause_of_death_observation_resource(
                        gpx=gpx,
                        patient_fullurl=patient_url,
                        condition_spec_id=terminal_spec_id,
                        cause_code=cause_code,
                        effective=death_date,
                    )
                )

            if with_claims and patient_coverage_url is not None:
                claim_resources: list[dict] = []
                for encounter in [r for r in extras if r["resourceType"] == "Encounter"]:
                    encounter_url = fullurl_for_resource(gpx, encounter)
                    provider_url = (encounter.get("serviceProvider") or {}).get(
                        "reference"
                    )
                    claim = build_claim_resource(
                        gpx=gpx,
                        patient_fullurl=patient_url,
                        encounter_fullurl=encounter_url,
                        coverage_fullurl=patient_coverage_url,
                        encounter_id_value=encounter["id"],
                        encounter_class=encounter["class"]["code"],
                        created=today,
                        provider_fullurl=provider_url,
                    )
                    claim_url = fullurl_for_resource(gpx, claim)
                    eob = build_explanation_of_benefit_resource(
                        gpx=gpx,
                        patient_fullurl=patient_url,
                        encounter_fullurl=encounter_url,
                        coverage_fullurl=patient_coverage_url,
                        claim_fullurl=claim_url,
                        encounter_id_value=encounter["id"],
                        encounter_class=encounter["class"]["code"],
                        payer_type=patient_payer_type or "commercial",
                        created=today,
                        provider_fullurl=provider_url,
                        insurer_fullurl=patient_payer_org_url,
                    )
                    claim_resources.extend((claim, eob))
                extras.extend(claim_resources)

            if format is OutputFormat.FHIR_R4:
                bundle = build_bundle(gpx, patient, extras)
                (out / f"{gpx}.json").write_text(json.dumps(bundle, indent=2))
            elif format is OutputFormat.NDJSON:
                for resource in (patient, *extras):
                    rtype = resource["resourceType"]
                    rid = resource.get("id", "")
                    if (
                        patient_payer_id is not None
                        and rtype in ("Organization", "InsurancePlan")
                        and patient_payer_id in emitted_payer_ids_ndjson
                    ):
                        continue
                    if rtype in (
                        "Practitioner",
                        "PractitionerRole",
                        "Location",
                        "Organization",
                    ) and rid in emitted_provider_ids_ndjson:
                        continue
                    fh = ndjson_files.get(rtype)
                    if fh is None:
                        fh = (out / f"{rtype}.ndjson").open("w", encoding="utf-8")
                        ndjson_files[rtype] = fh
                    fh.write(json.dumps(resource) + "\n")
                    if rtype in (
                        "Practitioner",
                        "PractitionerRole",
                        "Location",
                        "Organization",
                    ):
                        emitted_provider_ids_ndjson.add(rid)
                if patient_payer_id is not None:
                    emitted_payer_ids_ndjson.add(patient_payer_id)
            else:  # PARQUET
                for resource in (patient, *extras):
                    rtype = resource["resourceType"]
                    rid = resource.get("id", "")
                    if (
                        patient_payer_id is not None
                        and rtype in ("Organization", "InsurancePlan")
                        and patient_payer_id in emitted_payer_ids_ndjson
                    ):
                        continue
                    if rtype in (
                        "Practitioner",
                        "PractitionerRole",
                        "Location",
                        "Organization",
                    ) and rid in emitted_provider_ids_ndjson:
                        continue
                    subject_ref = None
                    if rtype != "Patient":
                        subj = resource.get("subject")
                        if isinstance(subj, dict):
                            subject_ref = subj.get("reference")
                    parquet_rows.setdefault(rtype, []).append(
                        {
                            "id": resource.get("id"),
                            "subject_reference": subject_ref,
                            "raw_json": json.dumps(resource),
                        }
                    )
                    if rtype in (
                        "Practitioner",
                        "PractitionerRole",
                        "Location",
                        "Organization",
                    ):
                        emitted_provider_ids_ndjson.add(rid)
                if patient_payer_id is not None:
                    emitted_payer_ids_ndjson.add(patient_payer_id)

            bracket = _bracket_for_age(age_years, summary_brackets)
            if bracket is not None:
                age_counter[bracket] += 1
            sex_counter[demo.gender.value] += 1
            race_counter[race_display(demo.race)] += 1
    finally:
        for fh in ndjson_files.values():
            fh.close()

    if format is OutputFormat.FHIR_R4:
        console.print(
            f"[green]✓[/green] Wrote {patients} patient bundle"
            f"{'s' if patients != 1 else ''} to [bold]{out}[/bold]"
        )
    elif format is OutputFormat.NDJSON:
        rtypes = sorted(ndjson_files.keys())
        console.print(
            f"[green]✓[/green] Wrote {patients} patient"
            f"{'s' if patients != 1 else ''} to [bold]{out}[/bold] "
            f"as NDJSON ({', '.join(f'{rt}.ndjson' for rt in rtypes)})"
        )
    else:  # PARQUET
        import pyarrow as pa
        import pyarrow.parquet as pq

        schema = pa.schema(
            [
                ("id", pa.string()),
                ("subject_reference", pa.string()),
                ("raw_json", pa.string()),
            ]
        )
        for rtype, rows in sorted(parquet_rows.items()):
            table = pa.Table.from_pylist(rows, schema=schema)
            pq.write_table(table, out / f"{rtype}.parquet")
        rtypes = sorted(parquet_rows.keys())
        console.print(
            f"[green]✓[/green] Wrote {patients} patient"
            f"{'s' if patients != 1 else ''} to [bold]{out}[/bold] "
            f"as Parquet ({', '.join(f'{rt}.parquet' for rt in rtypes)})"
        )

    if summary:
        _print_generate_summary(
            patients=patients,
            age_counter=age_counter,
            sex_counter=sex_counter,
            race_counter=race_counter,
            condition_counter=condition_counter,
            summary_brackets=summary_brackets,
            modules=[m.name for m in active_modules],
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
    table = Table(title="Bundled APEX Atlas modules")
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
def report(
    path: Annotated[Path, typer.Argument(help="Path to generated cohort (FHIR R4 bundles or NDJSON dir).")],
    out: Annotated[Path, typer.Option("--out", "-o", help="Destination HTML file.")] = Path("./cohort-report.html"),
    module: Annotated[str | None, typer.Option(help="Module whose bundled expectation to evaluate. Omit for demographics only.")] = None,
    min_samples: Annotated[int, typer.Option(help="Minimum bracket N for fidelity metrics; smaller brackets are skipped.")] = 30,
    as_of: Annotated[str | None, typer.Option(help="ISO date used as the reference for age computation.")] = None,
) -> None:
    """Build a self-contained HTML cohort report.

    Always reports demographics (age, sex) and per-code condition counts. When
    `--module NAME` is supplied, also runs the cohort fidelity harness and
    embeds a pass/fail table with target / actual / tolerance per metric.

    The output is a single HTML file with inline CSS, no JS, and no network
    calls — safe to email, archive, or commit to a release notes folder.
    """
    if not path.exists():
        err_console.print(f"[red]path does not exist:[/red] {path}")
        raise typer.Exit(code=1)

    expectation = None
    if module is not None:
        try:
            expectation = load_bundled_expectation(module)
        except ExpectationError as exc:
            err_console.print(f"[red]{exc}[/red]")
            raise typer.Exit(code=1) from exc

    reference_date = date.fromisoformat(as_of) if as_of else None
    demographics, fidelity = write_report(
        path,
        out,
        expectation=expectation,
        min_samples=min_samples,
        reference_date=reference_date,
    )

    if demographics.total_patients == 0:
        err_console.print(f"[yellow]No patients found under[/yellow] {path}")
        raise typer.Exit(code=1)

    console.print(
        f"[green]✓[/green] Wrote cohort report to [bold]{out}[/bold] "
        f"({demographics.total_patients:,} patient"
        f"{'s' if demographics.total_patients != 1 else ''})"
    )
    if fidelity is not None:
        passed = sum(1 for r in fidelity.results if r.within_tolerance)
        failed = len(fidelity.failing_metrics)
        status_color = "green" if fidelity.passed else "red"
        console.print(
            f"  fidelity: [{status_color}]{passed} passed, {failed} failed[/{status_color}], "
            f"{len(fidelity.skipped)} skipped"
        )
        raise typer.Exit(code=0 if fidelity.passed else 1)


@app.command()
def version() -> None:
    """Print the installed APEX Atlas version."""
    console.print(f"apex-atlas {__version__}")


@app.command()
def status() -> None:
    """Print implementation status of each subsystem."""
    table = Table(title="APEX Atlas — implementation status", show_lines=False)
    table.add_column("Component", style="bold")
    table.add_column("Status")
    table.add_column("Milestone")

    rows = [
        ("GPX identifier",        "[green]implemented[/green]",    "M0"),
        ("CLI scaffolding",       "[green]implemented[/green]",    "M0"),
        ("Demographic sampling",  "[green]ACS-sourced[/green]",   "M1"),
        ("FHIR Patient builder",  "[green]implemented[/green]",    "M1"),
        ("FHIR Condition builder","[green]implemented[/green]",    "M1"),
        ("FHIR Observation",      "[green]implemented[/green]",    "M2"),
        ("FHIR Encounter",        "[green]implemented[/green]",    "M2"),
        ("FHIR MedicationRequest","[green]implemented[/green]",    "M2"),
        ("FHIR Allergy/Immunization","[green]implemented[/green]", "M2"),
        ("FHIR DiagnosticReport", "[green]implemented[/green]",    "M2"),
        ("Claim + EOB",           "[green]first cut[/green]",      "M2"),
        ("atlas generate",        "[green]implemented[/green]",    "M1"),
        ("atlas validate",        "[green]structural[/green]",     "M1"),
        ("atlas validate --cohort","[green]first cut[/green]",      "M2"),
        ("Module runtime",        "[green]cross-module reqs[/green]", "M2"),
        ("Module library",        "[green]11 modules[/green]",     "M2"),
        ("Fidelity harness",      "[green]11 modules[/green]",     "M2"),
        ("LLM authoring",         "[dim]not started[/dim]",        "M3"),
        ("Clinical notes",        "[green]template[/green]",       "M4"),
    ]
    for row in rows:
        table.add_row(*row)
    console.print(table)


@ingest_app.command("prevalence")
def ingest_prevalence_cmd(
    input: Annotated[Path, typer.Option("--input", "-i", help="Input CSV with prevalence rows.")],
    metadata: Annotated[Path, typer.Option("--metadata", "-m", help="Metadata YAML carrying module, tolerance, and citations.")],
    output: Annotated[Path | None, typer.Option("--output", "-o", help="Destination path. Omit to print the rendered YAML to stdout.")] = None,
    overwrite: Annotated[bool, typer.Option("--overwrite", help="Allow overwriting an existing --output file.")] = False,
) -> None:
    """Build a fidelity expectation YAML from a prevalence CSV + metadata YAML.

    The ingest path enforces `provenance` of `sourced` or `verified` — placeholder
    expectations should be authored by hand. Output is round-tripped through the
    expectation loader before being written, so malformed metadata fails at ingest
    time rather than at `atlas validate --cohort` time.
    """
    from parker_atlas.ingest.prevalence import IngestionError, ingest_prevalence

    if not input.exists():
        err_console.print(f"[red]input CSV does not exist:[/red] {input}")
        raise typer.Exit(code=1)
    if not metadata.exists():
        err_console.print(f"[red]metadata YAML does not exist:[/red] {metadata}")
        raise typer.Exit(code=1)

    try:
        expectation_yaml = ingest_prevalence(input, metadata)
    except IngestionError as exc:
        err_console.print(f"[red]ingest failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    if output is None:
        console.print(expectation_yaml, end="", highlight=False)
        return

    if output.exists() and not overwrite:
        err_console.print(
            f"[red]{output} already exists[/red]. Pass --overwrite to replace."
        )
        raise typer.Exit(code=1)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(expectation_yaml, encoding="utf-8")
    console.print(f"[green]✓[/green] Wrote {output}")


@ingest_app.command("demographics")
def ingest_demographics_cmd(
    input: Annotated[Path, typer.Option("--input", "-i", help="Input CSV (age_sex / race / ethnicity shape).")],
    metadata: Annotated[Path, typer.Option("--metadata", "-m", help="Metadata YAML declaring `table` and provenance / citations.")],
    output: Annotated[Path, typer.Option("--output", "-o", help="Destination CSV path. The sibling <basename>.provenance.yaml is written alongside.")],
    overwrite: Annotated[bool, typer.Option("--overwrite", help="Allow overwriting existing output files.")] = False,
) -> None:
    """Ingest a demographic reference CSV (ACS, Census) into references/tables/.

    Writes two files next to each other:
    - the validated CSV at --output,
    - a <basename>.provenance.yaml sidecar carrying the citation chain.
    """
    from parker_atlas.ingest.demographics import ingest_demographics
    from parker_atlas.ingest.prevalence import IngestionError

    if not input.exists():
        err_console.print(f"[red]input CSV does not exist:[/red] {input}")
        raise typer.Exit(code=1)
    if not metadata.exists():
        err_console.print(f"[red]metadata YAML does not exist:[/red] {metadata}")
        raise typer.Exit(code=1)

    try:
        table, csv_content, provenance_yaml = ingest_demographics(input, metadata)
    except IngestionError as exc:
        err_console.print(f"[red]ingest failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    provenance_path = output.with_suffix(".provenance.yaml")
    existing = [p for p in (output, provenance_path) if p.exists()]
    if existing and not overwrite:
        err_console.print(
            f"[red]output files already exist:[/red] "
            f"{', '.join(str(p) for p in existing)}. Pass --overwrite to replace."
        )
        raise typer.Exit(code=1)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(csv_content, encoding="utf-8")
    provenance_path.write_text(provenance_yaml, encoding="utf-8")
    console.print(f"[green]✓[/green] Wrote {output}")
    console.print(f"[green]✓[/green] Wrote {provenance_path}")
    console.print(f"  table: [bold]{table}[/bold]")


@ingest_app.command("progression")
def ingest_progression_cmd(
    input: Annotated[Path, typer.Option("--input", "-i", help="Input CSV with progression rows (from, to, after_years, probability).")],
    metadata: Annotated[Path, typer.Option("--metadata", "-m", help="Metadata YAML carrying module name, version, and source citations.")],
    output: Annotated[Path | None, typer.Option("--output", "-o", help="Destination path. Omit to print the rendered overlay YAML to stdout.")] = None,
    overwrite: Annotated[bool, typer.Option("--overwrite", help="Allow overwriting an existing --output file.")] = False,
) -> None:
    """Build a progressions-overlay YAML from a CSV + metadata YAML.

    The overlay overrides matching `(from, to)` progression rates declared
    inline in the bundled module YAML. Adding new progressions via overlay
    is rejected — that requires a module YAML edit. The ingest path
    enforces `provenance` of `sourced` or `verified` (hand-authored
    placeholder rates belong inline in the module).

    Output is round-tripped through `apply_progressions_overlay` against
    the matching bundled module before being written, so unknown
    `(from, to)` pairs and bad rate values fail at ingest time rather
    than at module-load time.
    """
    from parker_atlas.ingest.progression import IngestionError, ingest_progression

    if not input.exists():
        err_console.print(f"[red]input CSV does not exist:[/red] {input}")
        raise typer.Exit(code=1)
    if not metadata.exists():
        err_console.print(f"[red]metadata YAML does not exist:[/red] {metadata}")
        raise typer.Exit(code=1)

    try:
        overlay_yaml = ingest_progression(input, metadata)
    except IngestionError as exc:
        err_console.print(f"[red]ingest failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    if output is None:
        console.print(overlay_yaml, end="", highlight=False)
        return

    if output.exists() and not overwrite:
        err_console.print(
            f"[red]{output} already exists[/red]. Pass --overwrite to replace."
        )
        raise typer.Exit(code=1)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(overlay_yaml, encoding="utf-8")
    console.print(f"[green]✓[/green] Wrote {output}")


if __name__ == "__main__":
    app()

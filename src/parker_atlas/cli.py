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
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Annotated, Any
import uuid

import typer
from rich.console import Console
from rich.progress import track
from rich.table import Table

from parker_atlas import __version__
from parker_atlas.core.demographics import race_display, sample_demographics
from parker_atlas.core.payer import sample_payer
from parker_atlas.core.sdoh import sample_sdoh
from parker_atlas.fhir.allergy_intolerance import build_allergy_intolerance_resource
from parker_atlas.fhir.bundle import build_bundle, fullurl_for_gpx, fullurl_for_resource
from parker_atlas.fhir.carin_bb import enrich_carin_bb
from parker_atlas.fhir.claim import (
    build_claim_resource,
    build_explanation_of_benefit_resource,
)
from parker_atlas.fhir.condition import build_condition_resource
from parker_atlas.fhir.coverage import build_coverage_resource
from parker_atlas.fhir.diagnostic_report import build_diagnostic_report_resource
from parker_atlas.fhir.insurance_plan import build_insurance_plan_resource
from parker_atlas.fhir.organization import build_payer_organization_resource
from parker_atlas.core.provider import sample_care_team
from parker_atlas.fhir.encounter import build_encounter_resource
from parker_atlas.fhir.location import build_location_resource
from parker_atlas.fhir.organization import build_facility_organization_resource
from parker_atlas.fhir.practitioner import build_practitioner_resource
from parker_atlas.fhir.practitioner_role import build_practitioner_role_resource
from parker_atlas.fhir.immunization import build_immunization_resource
from parker_atlas.fhir.medication_request import build_medication_request_resource
from parker_atlas.fhir.measure_report import (
    build_individual_measure_report,
    build_summary_measure_report,
)
from parker_atlas.fhir.mortality import build_cause_of_death_observation_resource
from parker_atlas.fhir.observation import (
    ObservationComponent,
    Quantity,
    build_observation_resource,
)
from parker_atlas.fhir.patient import build_patient_resource
from parker_atlas.fhir.procedure import build_procedure_resource
from parker_atlas.fhir.sdoh_observation import build_sdoh_observations
from parker_atlas.measures import (
    ALL_MEASURE_IDS,
    MEASURE_TITLES,
    MeasureTally,
    evaluate_measures,
)
from parker_atlas.notes import NoteStrategy
from parker_atlas.notes.emit import build_note_document_references
from parker_atlas.notes.types import parse_note_types
from parker_atlas.export.parquet_schema import PARQUET_SCHEMA_SPEC, PARQUET_SCHEMA_VERSION
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
from parker_atlas.validation.gtm import gtm_hardened_modules
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

author_app = typer.Typer(
    name="author",
    help="Research-grounded module authoring (dossier → draft module + expectation → promote).",
    no_args_is_help=True,
)
app.add_typer(author_app)

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


class RefStyle(str, Enum):
    """How inter-resource references are written in NDJSON output."""

    URN_UUID = "urn-uuid"   # urn:uuid:<uuid5> — self-consistent, matches bundles
    RELATIVE = "relative"   # Patient/<id> — idiomatic FHIR Bulk Data ($export)


def _relativize_references(node: Any, mapping: dict[str, str]) -> None:
    """Rewrite urn:uuid Reference.reference values to relative form, in place.

    `mapping` maps each urn:uuid fullUrl to its `ResourceType/id` relative
    reference. Walks the resource recursively so nested references (encounter,
    payor, result, participant, …) are all rewritten.
    """
    if isinstance(node, dict):
        ref = node.get("reference")
        if isinstance(ref, str) and ref in mapping:
            node["reference"] = mapping[ref]
        for value in node.values():
            _relativize_references(value, mapping)
    elif isinstance(node, list):
        for value in node:
            _relativize_references(value, mapping)


# Backwards-compatible alias — full launch-hardened set (see validation/gtm.py).
GTM_HARDENED_MODULES = gtm_hardened_modules()


LAUNCH_DEMO_MODULES = [
    "hypertension",
    "diabetes",
    "prediabetes",
    "hypercholesterolemia",
    "heart_failure",
    "asthma",
    "copd",
    "pneumonia",
    "covid19",
    "ckd",
    "urinary_tract_infection",
    "nephrolithiasis",
    "depression",
    "anxiety",
    "adult_immunizations",
    "pediatric_wellness",
    "maternal_health",
    "osteoporosis",
    "migraine",
    "gout",
    "psoriasis",
    "cataract",
    "hearing_loss",
    "fall_risk",
    "frailty",
]


def _write_generation_metadata(
    out: Path,
    *,
    cohort_id: str,
    generated_at: str,
    requested_patients: int,
    actual_patients: int,
    module_names: list[str],
    format: OutputFormat,
    profile: Profile,
    seed: int | None,
    as_of: str | None,
    ref_style: str | None,
    with_notes: bool,
    note_types: str | None,
    notes_strategy: NoteStrategy,
    llm_model: str | None,
    with_coverage: bool,
    with_providers: bool,
    with_claims: bool,
    with_sdoh: bool,
    with_measures: bool,
    carin_bb: bool = False,
    summary_counts: dict[str, Any] | None = None,
) -> None:
    metadata: dict[str, Any] = {
        "cohort_id": cohort_id,
        "generated_at": generated_at,
        "generated_by": "atlas generate",
        "version": __version__,
        "output_path": str(out),
        "requested_patients": requested_patients,
        "actual_patients": actual_patients,
        "module_names": module_names,
        "format": format.value,
        "profile": profile.value,
        "seed": seed,
        "as_of": as_of,
        "ref_style": ref_style,
        "with_notes": with_notes,
        "note_types": note_types,
        "notes_strategy": notes_strategy.value,
        "llm_model": llm_model,
        "with_coverage": with_coverage,
        "with_providers": with_providers,
        "with_claims": with_claims,
        "with_sdoh": with_sdoh,
        "with_measures": with_measures,
        "carin_bb": carin_bb,
    }
    if summary_counts is not None:
        metadata["summary"] = summary_counts
    if format is OutputFormat.PARQUET:
        metadata["parquet_schema_version"] = PARQUET_SCHEMA_VERSION

    out.mkdir(parents=True, exist_ok=True)
    (out / "generation-metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )


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
    measure_tallies: dict | None = None,
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

    if measure_tallies:
        meas_tbl = Table(title="Quality measures", show_edge=False)
        meas_tbl.add_column("Measure", style="bold")
        meas_tbl.add_column("Denom", justify="right")
        meas_tbl.add_column("Numer", justify="right")
        meas_tbl.add_column("Rate", justify="right")
        for tally in measure_tallies.values():
            if tally.denominator == 0:
                continue
            meas_tbl.add_row(
                tally.measure_title,
                str(tally.denominator),
                str(tally.numerator),
                f"{tally.rate:.1%}",
            )
        console.print(meas_tbl)


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


def _validate_refs(path: Path) -> None:
    """Cross-file referential-integrity check for a generated dataset."""
    from parker_atlas.validation.references import validate_references

    report = validate_references(path)

    if report.resources_scanned == 0:
        err_console.print(f"[yellow]No FHIR resources found under[/yellow] {path}")
        raise typer.Exit(code=1)

    for p, err in report.parse_errors:
        console.print(f"[red]parse error:[/red] {p}: {err}")

    if report.dangling:
        shown = report.dangling[:20]
        table = Table(title="Dangling references")
        table.add_column("From", style="bold")
        table.add_column("Unresolved reference")
        table.add_column("File")
        for d in shown:
            table.add_row(d.source, d.reference, Path(d.file).name)
        console.print(table)
        if len(report.dangling) > len(shown):
            console.print(f"  … and {len(report.dangling) - len(shown)} more")

    color = "green" if report.ok else "red"
    console.print(
        f"[{color}]{report.resolved}/{report.references_total} references resolved[/{color}] "
        f"across [bold]{report.resources_scanned}[/bold] resources in "
        f"[bold]{report.files_scanned}[/bold] file(s)."
    )
    if report.urn_uuid_unresolved:
        console.print(
            f"[yellow]{report.urn_uuid_unresolved} urn:uuid reference(s) did not resolve[/yellow] — "
            "urn:uuid links only resolve inside a transaction Bundle. For a "
            "cross-file NDJSON check, regenerate with "
            "[bold]atlas generate --ref-style relative[/bold]."
        )
    raise typer.Exit(code=0 if report.ok else 1)


def _validate_ig(
    path: Path, *, validator_jar: str | None, ig_version: str, ig_report: Path | None
) -> None:
    """IG conformance harness: native checks + optional external HL7 validator."""
    from parker_atlas.validation.ig import render_report, run_ig_validation

    report = run_ig_validation(path, validator_jar=validator_jar, ig_version=ig_version)
    if report.resources_scanned == 0:
        err_console.print(f"[yellow]No FHIR resources found under[/yellow] {path}")
        raise typer.Exit(code=1)

    struct_ok = report.resources_scanned - len(report.structural_invalid)
    console.print(
        f"Structural: [bold]{struct_ok}/{report.resources_scanned}[/bold] valid · "
        f"References: [bold]{report.ref_report.resolved}/{report.ref_report.references_total}[/bold] resolved · "
        f"Profiles: [bold]{len(report.profiles)}[/bold] distinct"
    )
    if report.external.ran:
        ext_status = "[green]PASS[/green]" if report.external.passed else "[red]FAIL[/red]"
        console.print(f"External HL7 validator: {ext_status}")
    else:
        console.print(f"[yellow]External HL7 validator not run[/yellow] — {report.external.reason}")

    if ig_report is not None:
        ig_report.parent.mkdir(parents=True, exist_ok=True)
        ig_report.write_text(render_report(report, dataset=str(path)), encoding="utf-8")
        console.print(f"[green]✓[/green] Wrote conformance report to [bold]{ig_report}[/bold]")

    color = "green" if report.ok else "red"
    console.print(f"[{color}]IG conformance: {'PASS' if report.ok else 'FAIL'}[/{color}]")
    raise typer.Exit(code=0 if report.ok else 1)


def _validate_gtm(path: Path, *, min_samples: int, as_of: str | None) -> None:
    """Run structural validation plus all launch-hardened cohort expectations."""

    summary = validate_path(path)
    console.print(
        f"Structural validation: [bold]{summary.total}[/bold] file(s), "
        f"[green]{summary.passed} passed[/green], "
        f"[red]{summary.failed} failed[/red], "
        f"[yellow]{summary.warnings} warning(s)[/yellow]"
    )
    if summary.total == 0:
        err_console.print(f"[yellow]No JSON files found under[/yellow] {path}")
        raise typer.Exit(code=1)

    reference_date = date.fromisoformat(as_of) if as_of else None
    table = Table(title="GTM fidelity expectations")
    table.add_column("Module", style="bold")
    table.add_column("Patients", justify="right")
    table.add_column("Bundles", justify="right")
    table.add_column("Passed", justify="right")
    table.add_column("Failed", justify="right")
    table.add_column("Skipped", justify="right")
    table.add_column("Status")

    cohort_failed = False
    for module_name in GTM_HARDENED_MODULES:
        try:
            expectation = load_bundled_expectation(module_name)
        except ExpectationError as exc:
            err_console.print(f"[red]{module_name}: {exc}[/red]")
            cohort_failed = True
            continue

        report = evaluate_cohort(
            path,
            expectation,
            min_samples=min_samples,
            reference_date=reference_date,
        )
        passed = sum(1 for r in report.results if r.within_tolerance)
        failed = len(report.failing_metrics)
        if failed:
            cohort_failed = True
        status = "[green]OK[/green]" if report.passed else "[red]FAIL[/red]"
        table.add_row(
            module_name,
            str(report.total_patients),
            str(report.bundles_scanned),
            str(passed),
            str(failed),
            str(len(report.skipped)),
            status,
        )

    console.print(table)
    failed = summary.failed > 0 or cohort_failed
    raise typer.Exit(code=1 if failed else 0)


@app.command()
def generate(
    patients: Annotated[int, typer.Option(help="Number of patients to generate.")] = 1000,
    out: Annotated[Path, typer.Option(help="Output directory.")] = Path("./patients"),
    format: Annotated[OutputFormat, typer.Option(help="Output format.")] = OutputFormat.FHIR_R4,
    module: Annotated[str | None, typer.Option(help="Module(s) to run, comma-separated for multiple (e.g. hypertension,complications).")] = None,
    profile: Annotated[Profile, typer.Option(help="FHIR profile to conform to.")] = Profile.US_CORE_6_1,
    seed: Annotated[int | None, typer.Option(help="RNG seed for reproducibility.")] = None,
    as_of: Annotated[str | None, typer.Option("--as-of", help="ISO date used as 'today' for age, onset, and measure periods. Pin it (with --seed) for fully reproducible cohorts that don't drift day to day. Defaults to the current date.")] = None,
    ref_style: Annotated[RefStyle, typer.Option("--ref-style", help="NDJSON reference style: 'urn-uuid' (default) or 'relative' (Patient/<id>) for idiomatic FHIR Bulk Data ($export) consumers. Ignored for fhir-r4 bundles (which require urn:uuid fullUrls).")] = RefStyle.URN_UUID,
    summary: Annotated[bool, typer.Option("--summary", help="Print cohort demographics and condition summary after generation.")] = False,
    with_notes: Annotated[bool, typer.Option("--with-notes", help="Emit clinical notes as DocumentReference resources.")] = False,
    note_types: Annotated[str | None, typer.Option("--note-types", help="Comma-separated note types when --with-notes is set: progress, discharge, radiology. Default: progress.")] = None,
    notes_strategy: Annotated[NoteStrategy, typer.Option("--notes-strategy", help="Strategy for progress notes: 'template' (deterministic, no API) or 'llm' (narrative via ATLAS_LLM_PROVIDER; requires API key).")] = NoteStrategy.TEMPLATE,
    llm_model: Annotated[str | None, typer.Option("--llm-model", help="LLM model id for --notes-strategy=llm (provider-specific; defaults to the fast tier for the selected ATLAS_LLM_PROVIDER).")] = None,
    with_coverage: Annotated[bool, typer.Option("--with-coverage", help="Sample a payer per patient and emit Coverage + payer Organization + InsurancePlan resources.")] = False,
    with_providers: Annotated[bool, typer.Option("--with-providers", help="Sample a Practitioner + facility Organization + Location per encounter; attach as Encounter.participant / .location / .serviceProvider.")] = False,
    with_claims: Annotated[bool, typer.Option("--with-claims", help="Emit one Claim + ExplanationOfBenefit per Encounter. Requires --with-coverage; uninsured patients receive no claims.")] = False,
    with_sdoh: Annotated[bool, typer.Option("--with-sdoh", help="Sample SDoH risk factors per patient (food insecurity, housing, transport, financial strain, social support) and emit Gravity Project SDOHCC Observations. SDoH domains causally reduce outpatient encounter and medication adherence rates.")] = False,
    with_measures: Annotated[bool, typer.Option("--with-measures", help="Emit DEQM MeasureReport resources: one individual report per patient per applicable measure, plus a population-level summary MeasureReport per measure at the end of the run.")] = False,
    carin_bb: Annotated[bool, typer.Option("--carin-bb", help="Stamp CARIN Blue Button (C4BB) profiles + required top-level elements onto Patient / Coverage / payer Organization / ExplanationOfBenefit. Requires --with-coverage (EOB parts also need --with-claims). Alignment with the CMS Interoperability rule, not full IG-validated conformance.")] = False,
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
    if carin_bb and not with_coverage:
        err_console.print(
            "[red]--carin-bb requires --with-coverage[/red] "
            "(add --with-claims for ExplanationOfBenefit enrichment too)."
        )
        raise typer.Exit(code=1)
    try:
        parsed_note_types = parse_note_types(note_types)
    except ValueError as exc:
        err_console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    note_types_label = note_types if note_types else "progress"
    active_modules = []
    if module is not None:
        for name in [m.strip() for m in module.split(",") if m.strip()]:
            try:
                active_modules.append(load_module(name))
            except ModuleError as exc:
                err_console.print(f"[red]{exc}[/red]")
                raise typer.Exit(code=1) from exc

    try:
        today = date.fromisoformat(as_of) if as_of else date.today()
    except ValueError as exc:
        err_console.print(f"[red]invalid --as-of:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    allocator = Allocator(Category.SYNTHETIC)

    measure_period_start = today.replace(month=1, day=1)
    measure_period_end = today.replace(month=12, day=31)

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

    # MeasureReport tallies — one per measure, accumulated across all patients.
    measure_tallies: dict[str, MeasureTally] = {
        mid: MeasureTally(measure_id=mid, measure_title=MEASURE_TITLES[mid])
        for mid in ALL_MEASURE_IDS
    }

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
            # SDoH profile — sampled before module runs so causal modifiers
            # are available when building emitted resources.
            sdoh_profile = sample_sdoh(rng, age_years=age_years) if with_sdoh else None

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
                # SDoH causal filter: probabilistically drop AMB Encounters
                # (transport/cost barriers) and MedicationRequests (adherence)
                # when SDoH risk is present. IMP and EMER encounters are not
                # affected — those represent care sought despite barriers.
                if sdoh_profile is not None:
                    filtered: list[dict] = []
                    for r in dx_emits:
                        rtype = r.get("resourceType")
                        if rtype == "Encounter":
                            enc_class = r.get("class", {}).get("code", "")
                            if enc_class == "AMB" and rng.random() > sdoh_profile.encounter_completion_rate:
                                continue  # patient missed this outpatient visit
                        elif rtype == "MedicationRequest":
                            if rng.random() > sdoh_profile.medication_adherence_rate:
                                continue  # patient did not fill this prescription
                        filtered.append(r)
                    dx_emits = filtered
                extras.extend(dx_emits)
                if with_notes:
                    try:
                        extras.extend(
                            build_note_document_references(
                                gpx=gpx,
                                patient_url=patient_url,
                                mod_name=mod_name,
                                patient_display_name=(
                                    f"{demo.family_name}, {demo.given_name}"
                                ),
                                age_years=age_years,
                                sex=demo.gender.value,
                                today=today,
                                all_diagnoses=all_diagnoses,
                                dx=dx,
                                dx_emits=dx_emits,
                                note_types=parsed_note_types,
                                notes_strategy=notes_strategy,
                                llm_model=llm_model,
                            )
                        )
                    except Exception as exc:
                        from parker_atlas.notes import LLMNotesUnavailable

                        if isinstance(exc, LLMNotesUnavailable):
                            err_console.print(
                                f"[red]LLM note authoring failed:[/red] {exc}"
                            )
                            raise typer.Exit(code=1) from exc
                        raise

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

            # SDoH FHIR Observations — always emit all 5 domains (positive and
            # negative) so downstream can distinguish screened-negative from
            # not-screened. Emitted after module resources so SDoH records
            # don't interfere with encounter linking.
            if sdoh_profile is not None:
                extras.extend(
                    build_sdoh_observations(
                        gpx=gpx,
                        patient_fullurl=patient_url,
                        profile=sdoh_profile,
                        effective=today,
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

            # Quality MeasureReport — evaluate all measures for this patient
            # and emit individual MeasureReport resources into the bundle.
            if with_measures:
                patient_measure_results = evaluate_measures(
                    age_years=age_years,
                    sex=demo.gender.value,
                    resources=extras,
                )
                for result in patient_measure_results:
                    measure_tallies[result.measure_id].add(result)
                    indv_report = build_individual_measure_report(
                        gpx=gpx,
                        patient_fullurl=patient_url,
                        measure_id=result.measure_id,
                        measure_title=MEASURE_TITLES[result.measure_id],
                        in_initial_population=result.in_initial_population,
                        in_denominator=result.in_denominator,
                        in_numerator=result.in_numerator,
                        period_start=measure_period_start,
                        period_end=measure_period_end,
                    )
                    extras.append(indv_report)

            if carin_bb:
                enrich_carin_bb([patient, *extras])

            if format is OutputFormat.FHIR_R4:
                bundle = build_bundle(gpx, patient, extras)
                (out / f"{gpx}.json").write_text(json.dumps(bundle, indent=2))
            elif format is OutputFormat.NDJSON:
                if ref_style is RefStyle.RELATIVE:
                    ref_map = {
                        fullurl_for_gpx(gpx): f"Patient/{patient['id']}",
                    }
                    for res in extras:
                        ref_map[fullurl_for_resource(gpx, res)] = (
                            f"{res['resourceType']}/{res.get('id', '')}"
                        )
                    for resource in (patient, *extras):
                        _relativize_references(resource, ref_map)
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

    # Population-level summary MeasureReports — one JSON file per measure
    # (fhir-r4 format) or appended to MeasureReport.ndjson/parquet.
    if with_measures:
        summary_reports = [
            build_summary_measure_report(
                measure_id=tally.measure_id,
                measure_title=tally.measure_title,
                initial_population_count=tally.initial_population,
                denominator_count=tally.denominator,
                numerator_count=tally.numerator,
                period_start=measure_period_start,
                period_end=measure_period_end,
            )
            for tally in measure_tallies.values()
        ]
        if format is OutputFormat.FHIR_R4:
            for report in summary_reports:
                (out / f"MeasureReport-{report['id']}.json").write_text(
                    json.dumps(report, indent=2)
                )
        elif format is OutputFormat.NDJSON:
            with (out / "MeasureReport-summary.ndjson").open("w", encoding="utf-8") as fh:
                for report in summary_reports:
                    fh.write(json.dumps(report) + "\n")
        else:  # PARQUET — append to parquet_rows for the flush below
            for report in summary_reports:
                parquet_rows.setdefault("MeasureReport", []).append(
                    {
                        "id": report.get("id"),
                        "subject_reference": None,
                        "raw_json": json.dumps(report),
                    }
                )

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
        (out / "parquet-schema.json").write_text(
            json.dumps(PARQUET_SCHEMA_SPEC, indent=2) + "\n",
            encoding="utf-8",
        )
        rtypes = sorted(parquet_rows.keys())
        console.print(
            f"[green]✓[/green] Wrote {patients} patient"
            f"{'s' if patients != 1 else ''} to [bold]{out}[/bold] "
            f"as Parquet ({', '.join(f'{rt}.parquet' for rt in rtypes)})"
        )
    cohort_id = (
        f"atlas-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
        f"-{uuid.uuid4().hex[:8]}"
    )
    generation_metadata: dict[str, Any] | None = None
    if summary:
        generation_metadata = {
            "age_brackets": {
                f"{lo}-{hi}": age_counter.get((lo, hi), 0)
                for lo, hi in summary_brackets
            },
            "sex": dict(sorted(sex_counter.items(), key=lambda kv: -kv[1])),
            "race": dict(sorted(race_counter.items(), key=lambda kv: -kv[1])),
            "conditions": dict(condition_counter.most_common()),
        }

    _write_generation_metadata(
        out,
        cohort_id=cohort_id,
        generated_at=datetime.now(timezone.utc).isoformat(),
        requested_patients=patients,
        actual_patients=patients,
        module_names=[m.name for m in active_modules],
        format=format,
        profile=profile,
        seed=seed,
        as_of=today.isoformat(),
        ref_style=ref_style.value if format is OutputFormat.NDJSON else None,
        with_notes=with_notes,
        note_types=note_types_label,
        notes_strategy=notes_strategy,
        llm_model=llm_model,
        with_coverage=with_coverage,
        with_providers=with_providers,
        with_claims=with_claims,
        with_sdoh=with_sdoh,
        with_measures=with_measures,
        carin_bb=carin_bb,
        summary_counts=generation_metadata,
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
            measure_tallies=measure_tallies if with_measures else None,
        )


@app.command("launch-demo")
def launch_demo(
    patients: Annotated[int, typer.Option(help="Number of demo patients to generate.")] = 2500,
    out: Annotated[Path, typer.Option(help="Output directory.")] = Path("./atlas-launch-demo"),
    seed: Annotated[int, typer.Option(help="RNG seed for reproducibility.")] = 20260522,
    summary: Annotated[bool, typer.Option("--summary", help="Print cohort demographics and condition summary after generation.")] = True,
) -> None:
    """Generate the curated launch-demo cohort used for GTM demos and screenshots."""

    generate(
        patients=patients,
        out=out,
        format=OutputFormat.FHIR_R4,
        module=",".join(LAUNCH_DEMO_MODULES),
        profile=Profile.US_CORE_6_1,
        seed=seed,
        summary=summary,
        with_notes=True,
        notes_strategy=NoteStrategy.TEMPLATE,
        llm_model=None,
        with_coverage=True,
        with_providers=True,
        with_claims=True,
        with_sdoh=True,
        with_measures=True,
    )


@app.command()
def validate(
    path: Annotated[Path, typer.Argument(help="Path to FHIR resources to validate.")],
    profile: Annotated[Profile, typer.Option(help="FHIR profile to validate against.")] = Profile.US_CORE_6_1,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Show per-file errors and warnings.")] = False,
    strict: Annotated[bool, typer.Option("--strict", help="Treat warnings as errors.")] = False,
    cohort: Annotated[bool, typer.Option("--cohort", help="Run cohort fidelity harness instead of per-file structural.")] = False,
    gtm: Annotated[bool, typer.Option("--gtm", help="Run structural validation plus all launch-hardened sourced expectations.")] = False,
    refs: Annotated[bool, typer.Option("--refs", help="Check cross-file referential integrity: every Type/id and Bundle fullUrl reference must resolve within the dataset. Works on NDJSON, $bulk-publish datasets, and R4 Bundles.")] = False,
    ig: Annotated[bool, typer.Option("--ig", help="Run the IG conformance harness: native structural + profile + reference checks, plus the external HL7 FHIR validator when a validator_cli.jar is available.")] = False,
    ig_report: Annotated[Path | None, typer.Option("--ig-report", help="Write the --ig conformance report (Markdown) to this file.")] = None,
    validator_jar: Annotated[str | None, typer.Option("--validator-jar", help="Path to the HL7 FHIR validator_cli.jar for --ig (else $ATLAS_FHIR_VALIDATOR_JAR or a local cache).")] = None,
    ig_version: Annotated[str, typer.Option("--ig-version", help="FHIR version passed to the external validator under --ig.")] = "4.0.1",
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

    `--gtm` runs structural validation and every launch-hardened sourced
    expectation in one pass.
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

    if refs:
        _validate_refs(path)
        return

    if ig:
        _validate_ig(path, validator_jar=validator_jar, ig_version=ig_version, ig_report=ig_report)
        return

    if gtm:
        _validate_gtm(path, min_samples=min_samples, as_of=as_of)
        return

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
        ("atlas validate --refs", "[green]referential[/green]",    "Diff-5"),
        ("atlas validate --ig",   "[green]native + HL7[/green]",   "Diff-5"),
        ("Module runtime",        "[green]cross-module reqs[/green]", "M2"),
        ("Module library",        "[green]100 modules[/green]",    "M2"),
        ("Fidelity harness",      "[green]18 sourced modules[/green]", "M2"),
        ("LLM authoring",         "[dim]not started[/dim]",        "M3"),
        ("Clinical notes",        "[green]template[/green]",       "M4"),
        ("SDoH overlay",          "[green]implemented[/green]",    "Diff-2"),
        ("Pediatric well-child",  "[green]implemented[/green]",    "Diff-1"),
        ("Maternal health / OB",  "[green]implemented[/green]",    "Diff-1"),
        ("Quality MeasureReport", "[green]implemented[/green]",    "Diff-3"),
        ("SMART Scheduling Links","[green]$bulk-publish[/green]",   "Diff-4"),
        ("Da Vinci Plan-Net",     "[green]$bulk-publish[/green]",   "Diff-5"),
        ("CARIN Blue Button",     "[green]C4BB alignment[/green]",  "Diff-5"),
        ("Reproducible --as-of",  "[green]implemented[/green]",     "Diff-5"),
        ("Relative NDJSON refs",  "[green]--ref-style[/green]",     "Diff-5"),
        ("Coherent provider ids", "[green]roster-shared[/green]",   "Diff-5"),
        ("CI pipeline",           "[green]pytest/ruff/mypy[/green]","Diff-5"),
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


# -- author ------------------------------------------------------------------


def _signoff_template(condition: str, dossier) -> str:  # noqa: ANN001 - Dossier
    """A clinician sign-off checklist. `atlas author promote` reads the
    `Signed-off-by:` line; a non-empty value unlocks promotion."""
    method = dossier.generated.get("method", "manual")
    return (
        f"# Clinician sign-off — `{condition}`\n\n"
        f"This module was auto-drafted by `atlas author` (method={method}) and is "
        f"**not shippable** until a licensed clinician reviews it and fills in the "
        f"`Signed-off-by:` line below.\n\n"
        f"## Review checklist\n\n"
        f"- [ ] SNOMED/ICD-10 codes correctly identify the condition\n"
        f"- [ ] Prevalence cells match the cited source table (age/sex bands and rates)\n"
        f"- [ ] Observation value ranges are clinically plausible and correctly coded (LOINC/units)\n"
        f"- [ ] Medication choices and treated-fraction reflect current standard of care\n"
        f"- [ ] Progressions (targets, timing, probabilities) are clinically sound and cited\n"
        f"- [ ] Every numeric claim traces to a citation in `dossier.yaml`\n\n"
        f"## Sign-off\n\n"
        f"Signed-off-by: \n"
        f"Date: \n"
        f"Notes: \n"
    )


@author_app.command("synthesize")
def author_synthesize_cmd(
    dossier: Annotated[Path, typer.Option("--dossier", "-d", help="Research dossier YAML to synthesize.")],
    out: Annotated[Path, typer.Option("--out", "-o", help="Staging directory for drafts.")] = Path("./atlas-drafts"),
    overwrite: Annotated[bool, typer.Option("--overwrite", help="Allow overwriting an existing draft directory's files.")] = False,
) -> None:
    """Synthesize a draft module + draft fidelity expectation from a dossier.

    Writes `<out>/<condition>/{<condition>.yaml, <condition>.expectation.yaml,
    dossier.yaml, SIGNOFF.md}`. Both generated artifacts are round-tripped
    through the real loaders, so a malformed dossier fails here rather than at
    `atlas generate` / `atlas validate` time. Drafts live outside the bundled
    library and are invisible to the runtime until `atlas author promote`.
    """
    from parker_atlas.author import (
        AuthorError,
        DossierError,
        load_dossier_from_str,
        synthesize_expectation,
        synthesize_module,
    )

    if not dossier.exists():
        err_console.print(f"[red]dossier does not exist:[/red] {dossier}")
        raise typer.Exit(code=1)

    dossier_text = dossier.read_text(encoding="utf-8")
    try:
        doc = load_dossier_from_str(dossier_text)
        module_yaml = synthesize_module(doc)
        expectation_yaml = synthesize_expectation(doc)
    except (DossierError, AuthorError) as exc:
        err_console.print(f"[red]author failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    draft_dir = out / doc.condition
    targets = {
        draft_dir / f"{doc.condition}.yaml": module_yaml,
        draft_dir / f"{doc.condition}.expectation.yaml": expectation_yaml,
        draft_dir / "dossier.yaml": dossier_text,
        draft_dir / "SIGNOFF.md": _signoff_template(doc.condition, doc),
    }
    existing = [p for p in targets if p.exists()]
    if existing and not overwrite:
        err_console.print(
            f"[red]draft files already exist:[/red] "
            f"{', '.join(str(p) for p in existing)}. Pass --overwrite to replace."
        )
        raise typer.Exit(code=1)

    draft_dir.mkdir(parents=True, exist_ok=True)
    for path, content in targets.items():
        path.write_text(content, encoding="utf-8")

    console.print(f"[green]✓[/green] Drafted [bold]{doc.condition}[/bold] → {draft_dir}")
    console.print(f"  module:      {draft_dir / f'{doc.condition}.yaml'}")
    console.print(f"  expectation: {draft_dir / f'{doc.condition}.expectation.yaml'}")
    console.print(
        f"  [yellow]Next:[/yellow] clinician review → fill `Signed-off-by:` in "
        f"{draft_dir / 'SIGNOFF.md'} → [bold]atlas author promote --draft {draft_dir}[/bold]"
    )


@author_app.command("promote")
def author_promote_cmd(
    draft: Annotated[Path, typer.Option("--draft", "-d", help="Draft directory produced by `atlas author synthesize`.")],
    overwrite: Annotated[bool, typer.Option("--overwrite", help="Allow replacing an existing library module/expectation.")] = False,
    force: Annotated[bool, typer.Option("--force", help="Promote even without a clinician sign-off (NOT recommended).")] = False,
) -> None:
    """Install a clinician-reviewed draft into the bundled library.

    Re-validates the reviewed module + expectation, refuses to proceed unless
    `SIGNOFF.md` carries a non-empty `Signed-off-by:` value (override with
    --force), strips the DRAFT banner, and writes both files into the shipping
    library + expectation directories.
    """
    from parker_atlas.author.promote import PromotionError, promote_draft

    try:
        module_path, expectation_path = promote_draft(
            draft, overwrite=overwrite, force=force
        )
    except PromotionError as exc:
        err_console.print(f"[red]promote failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    console.print(f"[green]✓[/green] Promoted [bold]{draft.name}[/bold] into the library")
    console.print(f"  module:      {module_path}")
    console.print(f"  expectation: {expectation_path}")
    console.print(
        f"  [yellow]Next:[/yellow] verify with "
        f"[bold]atlas validate --cohort --module {draft.name}[/bold] at a sufficient cohort size."
    )


@author_app.command("research")
def author_research_cmd(
    condition: Annotated[str, typer.Option("--condition", "-c", help="Condition / module name to research (snake_case).")],
    output: Annotated[Path | None, typer.Option("--output", "-o", help="Destination dossier file. Omit to print the dossier YAML to stdout.")] = None,
    model: Annotated[str | None, typer.Option("--model", help="Override the research model (default: Sonnet 4.6).")] = None,
    draft_out: Annotated[Path | None, typer.Option("--draft-out", help="If set, also synthesize a draft bundle into this staging dir.")] = None,
    overwrite: Annotated[bool, typer.Option("--overwrite", help="Allow overwriting an existing --output / draft file.")] = False,
) -> None:
    """Research a condition with an LLM + web_search and emit a validated dossier.

    The model searches authoritative public US sources, then returns a dossier
    matching the schema in docs/authoring/research_authoring.md; it is validated
    through the dossier loader before anything is written. Requires the
    `anthropic` extra and ANTHROPIC_API_KEY. With --draft-out, the dossier is
    fed straight into synthesis so you go from a condition name to a reviewable
    draft in one command.
    """
    from parker_atlas.author import (
        AuthorError,
        DossierError,
        load_dossier_from_str,
        synthesize_expectation,
        synthesize_module,
    )
    from parker_atlas.author.research import (
        AuthorResearchUnavailable,
        research_condition,
    )

    research_kwargs = {"model": model} if model else {}
    try:
        dossier_yaml = research_condition(condition, **research_kwargs)
    except AuthorResearchUnavailable as exc:
        err_console.print(f"[red]research failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    if output is not None:
        if output.exists() and not overwrite:
            err_console.print(f"[red]{output} already exists[/red]. Pass --overwrite to replace.")
            raise typer.Exit(code=1)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(dossier_yaml, encoding="utf-8")
        console.print(f"[green]✓[/green] Wrote dossier {output}")
    elif draft_out is None:
        console.print(dossier_yaml, end="", highlight=False)

    if draft_out is None:
        return

    # Convenience: chain research → synthesize so a condition name yields a draft.
    try:
        doc = load_dossier_from_str(dossier_yaml)
        module_yaml = synthesize_module(doc)
        expectation_yaml = synthesize_expectation(doc)
    except (DossierError, AuthorError) as exc:
        err_console.print(f"[red]author failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    draft_dir = draft_out / doc.condition
    targets = {
        draft_dir / f"{doc.condition}.yaml": module_yaml,
        draft_dir / f"{doc.condition}.expectation.yaml": expectation_yaml,
        draft_dir / "dossier.yaml": dossier_yaml,
        draft_dir / "SIGNOFF.md": _signoff_template(doc.condition, doc),
    }
    existing = [p for p in targets if p.exists()]
    if existing and not overwrite:
        err_console.print(
            f"[red]draft files already exist:[/red] "
            f"{', '.join(str(p) for p in existing)}. Pass --overwrite to replace."
        )
        raise typer.Exit(code=1)
    draft_dir.mkdir(parents=True, exist_ok=True)
    for path, content in targets.items():
        path.write_text(content, encoding="utf-8")
    console.print(f"[green]✓[/green] Researched + drafted [bold]{doc.condition}[/bold] → {draft_dir}")
    console.print(
        f"  [yellow]Next:[/yellow] clinician review → fill `Signed-off-by:` in "
        f"{draft_dir / 'SIGNOFF.md'} → [bold]atlas author promote --draft {draft_dir}[/bold]"
    )


def _load_patient_ids(path: Path) -> list[str]:
    """Read Patient.id values from a Patient.ndjson file or a cohort directory."""
    if path.is_dir():
        candidate = path / "Patient.ndjson"
        if not candidate.exists():
            raise typer.BadParameter(
                f"no Patient.ndjson under {path}; pass the file directly or a "
                f"directory produced by `atlas generate --format ndjson`."
            )
        path = candidate
    ids: list[str] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            ids.append(json.loads(line)["id"])
    return ids


@app.command("publish-scheduling")
def publish_scheduling(
    out: Annotated[Path, typer.Option("--out", "-o", help="Output directory for the bulk-publish dataset.")] = Path("./scheduling"),
    sites: Annotated[int, typer.Option(help="Number of clinic Locations to publish (1–40).")] = 25,
    service_types: Annotated[str, typer.Option("--service-types", help="Comma-separated service types: general-practice, immunization, mental-health.")] = "general-practice,immunization",
    window_start: Annotated[str | None, typer.Option("--window-start", help="ISO date the availability window opens (default: today).")] = None,
    weeks: Annotated[int, typer.Option(help="Number of weeks of availability (weekdays only).")] = 2,
    day_start_hour: Annotated[int, typer.Option("--day-start-hour", help="First slot start hour (local, 24h).")] = 8,
    day_end_hour: Annotated[int, typer.Option("--day-end-hour", help="Slots stop before this hour (local, 24h).")] = 17,
    slot_minutes: Annotated[int, typer.Option("--slot-minutes", help="Slot length in minutes.")] = 60,
    booked_fraction: Annotated[float, typer.Option("--booked-fraction", help="Fraction of slots marked busy (0–1).")] = 0.20,
    seed: Annotated[int | None, typer.Option(help="RNG seed for reproducibility.")] = None,
    base_url: Annotated[str, typer.Option("--base-url", help="Base URL the manifest advertises for its NDJSON output files.")] = "https://example.org/scheduling",
    booking_base_url: Annotated[str, typer.Option("--booking-base-url", help="Base URL used to build per-slot booking deep links.")] = "https://booking.example.org",
    patients: Annotated[Path | None, typer.Option("--patients", help="Patient.ndjson file or cohort dir; when set, booked slots get Appointment resources referencing these patients.")] = None,
) -> None:
    """Publish a SMART Scheduling Links (`$bulk-publish`) availability dataset.

    Emits a `bulk-publish-manifest.json` plus `Location.ndjson`,
    `Schedule.ndjson`, and `Slot.ndjson` conforming to the SMART Scheduling
    Links specification — the "SMART FHIR Scheduling" flow that advertises open,
    bookable appointment slots. Slots carry the SMART booking-deep-link,
    booking-phone, and slot-capacity extensions.

    With `--patients`, every busy slot is booked with an Appointment referencing
    a patient from the given cohort, written to `Appointment.ndjson` (a
    connectathon convenience; Appointment is not part of the manifest).
    """
    from parker_atlas.scheduling import (
        SchedulingConfig,
        generate_scheduling_dataset,
        write_bulk_publish,
    )

    keys = tuple(s.strip() for s in service_types.split(",") if s.strip())
    try:
        start = date.fromisoformat(window_start) if window_start else date.today()
    except ValueError as exc:
        err_console.print(f"[red]invalid --window-start:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    patient_ids: list[str] | None = None
    if patients is not None:
        if not patients.exists():
            err_console.print(f"[red]--patients path does not exist:[/red] {patients}")
            raise typer.Exit(code=1)
        try:
            patient_ids = _load_patient_ids(patients)
        except typer.BadParameter as exc:
            err_console.print(f"[red]{exc}[/red]")
            raise typer.Exit(code=1) from exc
        if not patient_ids:
            err_console.print(f"[yellow]no patients found under {patients}[/yellow]")
            raise typer.Exit(code=1)

    config = SchedulingConfig(
        sites=sites,
        service_keys=keys,
        window_start=start,
        weeks=weeks,
        day_start_hour=day_start_hour,
        day_end_hour=day_end_hour,
        slot_minutes=slot_minutes,
        booked_fraction=booked_fraction,
        seed=seed,
        booking_base_url=booking_base_url,
    )
    try:
        config.validate()
    except ValueError as exc:
        err_console.print(f"[red]invalid scheduling config:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    transaction_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    dataset = generate_scheduling_dataset(config, patient_ids=patient_ids)
    manifest_path = write_bulk_publish(
        dataset,
        out,
        base_url=base_url,
        transaction_time=transaction_time,
    )

    counts = dataset.counts
    console.print(
        f"[green]✓[/green] Published SMART Scheduling Links dataset to [bold]{out}[/bold]"
    )
    console.print(
        f"  Locations={counts['Location']} Schedules={counts['Schedule']} "
        f"Slots={counts['Slot']} (free={counts['Slot(free)']}, busy={counts['Slot(busy)']}) "
        f"Appointments={counts['Appointment']}"
    )
    console.print(f"  manifest: [bold]{manifest_path}[/bold]")


@app.command("publish-provider-directory")
def publish_provider_directory(
    out: Annotated[Path, typer.Option("--out", "-o", help="Output directory for the Plan-Net bulk-publish directory.")] = Path("./provider-directory"),
    base_url: Annotated[str, typer.Option("--base-url", help="Base URL the manifest advertises for its NDJSON output files.")] = "https://example.org/provider-directory",
    count: Annotated[int | None, typer.Option("--count", help="Number of practitioners. Omit for the shipped 150-clinician roster; a larger value synthesizes additional deterministic clinicians.")] = None,
    seed: Annotated[int, typer.Option("--seed", help="Seed for synthesized clinicians when --count exceeds the shipped roster.")] = 20260713,
) -> None:
    """Publish a Da Vinci PDEX Plan-Net provider directory (bulk NDJSON + manifest).

    Emits a `bulk-publish-manifest.json` plus per-type NDJSON (Organization —
    networks and providers — Location, Practitioner, PractitionerRole,
    HealthcareService, InsurancePlan, Endpoint) conforming to the Plan-Net
    profiles. This is the payer provider-directory surface referenced by the CMS
    Interoperability & Patient Access rule.

    The directory is built from the same provider roster patient encounters use
    (`atlas generate --with-providers`), so practitioner and facility NPIs match
    across claims and the directory.
    """
    from parker_atlas.provider_directory import (
        generate_provider_directory,
        write_bulk_publish,
    )

    transaction_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    directory = generate_provider_directory(count=count, seed=seed)
    manifest_path = write_bulk_publish(
        directory, out, base_url=base_url, transaction_time=transaction_time
    )
    counts = directory.counts
    console.print(
        f"[green]✓[/green] Published Plan-Net provider directory to [bold]{out}[/bold]"
    )
    console.print(
        "  " + " ".join(f"{k}={v}" for k, v in counts.items())
    )
    console.print(f"  manifest: [bold]{manifest_path}[/bold]")


@app.command()
def serve(
    host: Annotated[str, typer.Option("--host", help="Interface to bind (use 0.0.0.0 in a container).")] = "127.0.0.1",
    port: Annotated[int, typer.Option("--port", "-p", help="Port to listen on. Defaults to $PORT if set, else 8080.")] = 0,
) -> None:
    """Run the Apex Atlas dev API server (HTTP generation + FHIR Bulk Data $export).

    A single-process development server — not a production deployment. Endpoints:
    GET /health, GET /modules, GET /fhir/metadata, POST /generate (synchronous
    NDJSON), GET /fhir/$export (async kickoff) → poll GET /jobs/<id> → download
    GET /jobs/<id>/<Type>.ndjson. Patient count is capped per request.

    For container/PaaS deploys, bind `--host 0.0.0.0`; the port defaults to the
    platform-injected `$PORT` when `--port` is not given.
    """
    import os as _os

    from parker_atlas.server import serve as _serve

    if port == 0:
        port = int(_os.environ.get("PORT", "8080"))
    httpd = _serve(host, port)
    bound = httpd.server_address
    console.print(
        f"[green]Apex Atlas dev server[/green] listening on "
        f"http://{bound[0]}:{bound[1]}  (Ctrl-C to stop)"
    )
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        console.print("\n[yellow]shutting down[/yellow]")
        httpd.shutdown()


if __name__ == "__main__":
    app()

"""
IG conformance harness.

Produces a conformance report for a generated dataset with two layers:

1. **Native checks** (always run, no external deps): structural validation of
   every resource via the ``fhir.resources`` R4B models, a histogram of declared
   ``meta.profile`` canonicals, and cross-file referential integrity.
2. **External HL7 validator** (best-effort): if the official HL7 FHIR
   ``validator_cli.jar`` is available (``--validator-jar``, ``$ATLAS_FHIR_VALIDATOR_JAR``,
   or a local cache) and Java is on PATH, run it and fold its pass/fail into the
   report. Full IG (US Core / C4BB / Plan-Net) profile conformance requires this
   external validator; the native layer is a fast, dependency-free approximation.

Nothing here downloads by default; the external jar is used only if present.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from fhir.resources.R4B import get_fhir_model_class

from parker_atlas.validation.references import RefReport, _load, validate_references

_CACHE_JAR = Path.home() / ".cache" / "apex-atlas" / "validator_cli.jar"


@dataclass(slots=True)
class ExternalResult:
    ran: bool
    jar: str | None = None
    returncode: int | None = None
    output_tail: str = ""
    reason: str = ""

    @property
    def passed(self) -> bool:
        return self.ran and self.returncode == 0


@dataclass(slots=True)
class IgReport:
    resources_scanned: int = 0
    by_type: Counter[str] = field(default_factory=Counter)
    profiles: Counter[str] = field(default_factory=Counter)
    structural_invalid: list[tuple[str, str]] = field(default_factory=list)  # (key, error)
    ref_report: RefReport = field(default_factory=RefReport)
    external: ExternalResult = field(default_factory=lambda: ExternalResult(ran=False))

    @property
    def native_ok(self) -> bool:
        return not self.structural_invalid and self.ref_report.ok

    @property
    def ok(self) -> bool:
        # If the external validator ran, it must also pass.
        return self.native_ok and (not self.external.ran or self.external.passed)


def _resource_key(res: dict) -> str:
    return f"{res.get('resourceType', '?')}/{res.get('id', '?')}"


def locate_validator(explicit: str | None) -> str | None:
    """Find the HL7 validator jar: explicit arg, env var, then local cache."""
    for candidate in (explicit, os.environ.get("ATLAS_FHIR_VALIDATOR_JAR"), str(_CACHE_JAR)):
        if candidate and Path(candidate).is_file():
            return candidate
    return None


def _run_external(path: Path, jar: str, ig_version: str, igs: tuple[str, ...]) -> ExternalResult:
    java = shutil.which("java")
    if java is None:
        return ExternalResult(ran=False, jar=jar, reason="java not found on PATH")

    files = [str(path)] if path.is_file() else [
        str(p) for p in sorted([*path.rglob("*.ndjson"), *path.rglob("*.json")])
        if p.stem not in {"generation-metadata", "parquet-schema", "bulk-publish-manifest"}
    ]
    if not files:
        return ExternalResult(ran=False, jar=jar, reason="no resource files to validate")

    cmd = [java, "-jar", jar, *files, "-version", ig_version]
    for ig in igs:
        cmd += ["-ig", ig]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    except (subprocess.TimeoutExpired, OSError) as exc:
        return ExternalResult(ran=False, jar=jar, reason=f"validator failed to run: {exc}")
    tail = "\n".join((proc.stdout + proc.stderr).splitlines()[-250:])
    return ExternalResult(ran=True, jar=jar, returncode=proc.returncode, output_tail=tail)


def run_ig_validation(
    path: Path,
    *,
    validator_jar: str | None = None,
    ig_version: str = "4.0.1",
    igs: tuple[str, ...] = (),
    run_external: bool = True,
) -> IgReport:
    """Run native conformance checks (+ optional external HL7 validator)."""
    resources, _index, _errors = _load(path)
    report = IgReport()
    report.resources_scanned = len(resources)

    for _f, res in resources:
        rtype = res.get("resourceType", "?")
        report.by_type[rtype] += 1
        for profile in res.get("meta", {}).get("profile", []):
            report.profiles[profile] += 1
        try:
            get_fhir_model_class(rtype)(**res)
        except Exception as exc:  # collect any structural failure
            report.structural_invalid.append((_resource_key(res), str(exc).splitlines()[0]))

    report.ref_report = validate_references(path)

    if run_external:
        jar = locate_validator(validator_jar)
        if jar is None:
            report.external = ExternalResult(
                ran=False,
                reason="no validator_cli.jar found (pass --validator-jar or set "
                "ATLAS_FHIR_VALIDATOR_JAR); native checks only",
            )
        else:
            report.external = _run_external(path, jar, ig_version, igs)

    return report


def render_report(report: IgReport, *, dataset: str) -> str:
    """Render the IG report as Markdown."""
    lines: list[str] = []
    verdict = "PASS" if report.ok else "FAIL"
    lines.append(f"# IG conformance report — {verdict}")
    lines.append("")
    lines.append(f"Dataset: `{dataset}` — {report.resources_scanned} resources")
    lines.append("")

    lines.append("## Resource types")
    lines.append("")
    lines.append("| Type | Count |")
    lines.append("| --- | ---: |")
    for rtype, n in sorted(report.by_type.items()):
        lines.append(f"| {rtype} | {n} |")
    lines.append("")

    lines.append("## Declared profiles (`meta.profile`)")
    lines.append("")
    if report.profiles:
        lines.append("| Profile | Resources |")
        lines.append("| --- | ---: |")
        for profile, n in sorted(report.profiles.items()):
            lines.append(f"| `{profile}` | {n} |")
    else:
        lines.append("_No profiles declared._")
    lines.append("")

    lines.append("## Native checks")
    lines.append("")
    lines.append(
        f"- Structural (fhir.resources R4B): "
        f"**{report.resources_scanned - len(report.structural_invalid)}/{report.resources_scanned} valid**"
    )
    for key, err in report.structural_invalid[:20]:
        lines.append(f"  - `{key}`: {err}")
    rr = report.ref_report
    lines.append(
        f"- Referential integrity: **{rr.resolved}/{rr.references_total} references resolved**"
        + (f" ({len(rr.dangling)} dangling)" if rr.dangling else "")
    )
    lines.append("")

    lines.append("## External HL7 validator")
    lines.append("")
    ext = report.external
    if not ext.ran:
        lines.append(f"_Not run: {ext.reason}_")
        lines.append("")
        lines.append(
            "> Full US Core / C4BB / Plan-Net profile conformance requires the "
            "official HL7 FHIR validator. Provide it with `--validator-jar PATH` "
            "(or `$ATLAS_FHIR_VALIDATOR_JAR`) to include an external pass."
        )
    else:
        status = "PASS" if ext.passed else f"FAIL (exit {ext.returncode})"
        lines.append(f"- Validator: `{ext.jar}`")
        lines.append(f"- Result: **{status}**")
        if ext.output_tail:
            lines.append("")
            lines.append("```")
            lines.append(ext.output_tail)
            lines.append("```")
    lines.append("")
    return "\n".join(lines)

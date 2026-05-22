"""
Structural validation of generated FHIR output.

This module performs two layers of checks:

1. **Schema** — each resource round-trips through the relevant
   `fhir.resources.R4B` pydantic model. This catches cardinality errors,
   wrong datatypes, unknown fields, and similar schema-level faults.

2. **US Core 6.1 Patient minimums** — each Patient carries the elements
   that US Core marks as required or must-support (identifier, name,
   gender), plus Atlas-specific conventions (HTEST tag, US Core profile
   claim, US Core race/ethnicity/birthsex extensions).

Not implemented here:
- Full US Core profile validation against the official StructureDefinition
  (needs a real FHIR validator such as HAPI or Firely).
- Terminology binding checks against canonical value sets.
- Validation of non-Patient resources (added when Milestone 2 lands
  Encounter / Condition / Observation).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fhir.resources.R4B.bundle import Bundle as _Bundle
from fhir.resources.R4B.allergyintolerance import AllergyIntolerance as _Allergy
from fhir.resources.R4B.claim import Claim as _Claim
from fhir.resources.R4B.condition import Condition as _Condition
from fhir.resources.R4B.diagnosticreport import DiagnosticReport as _DiagReport
from fhir.resources.R4B.documentreference import DocumentReference as _DocRef
from fhir.resources.R4B.encounter import Encounter as _Encounter
from fhir.resources.R4B.explanationofbenefit import ExplanationOfBenefit as _EOB
from fhir.resources.R4B.immunization import Immunization as _Immunization
from fhir.resources.R4B.medicationrequest import MedicationRequest as _MedReq
from fhir.resources.R4B.observation import Observation as _Observation
from fhir.resources.R4B.patient import Patient as _Patient
from fhir.resources.R4B.procedure import Procedure as _Procedure

from parker_atlas.fhir.patient import (
    US_CORE_BIRTHSEX_URL,
    US_CORE_ETHNICITY_URL,
    US_CORE_PATIENT_PROFILE,
    US_CORE_RACE_URL,
)

# Map resourceType → fhir.resources R4B class for per-resource schema
# validation. Used by the NDJSON walker; the bundle walker validates
# transitively through Bundle.model_validate().
_FHIR_R4B_CLASSES: dict[str, type] = {
    "AllergyIntolerance": _Allergy,
    "Claim": _Claim,
    "Patient": _Patient,
    "Condition": _Condition,
    "DiagnosticReport": _DiagReport,
    "Encounter": _Encounter,
    "ExplanationOfBenefit": _EOB,
    "Immunization": _Immunization,
    "Observation": _Observation,
    "MedicationRequest": _MedReq,
    "DocumentReference": _DocRef,
    "Procedure": _Procedure,
}


@dataclass
class FileReport:
    path: Path
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


@dataclass
class ValidationSummary:
    files: list[FileReport] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.files)

    @property
    def passed(self) -> int:
        return sum(1 for f in self.files if f.ok)

    @property
    def failed(self) -> int:
        return self.total - self.passed

    @property
    def warnings(self) -> int:
        return sum(len(f.warnings) for f in self.files)


def _iter_json_files(path: Path) -> list[Path]:
    """Return JSON-Bundle and NDJSON files at or beneath `path`."""
    if path.is_file():
        return [path]
    return sorted(
        [
            *(
                candidate
                for candidate in path.rglob("*.json")
                if candidate.name != "generation-metadata.json"
            ),
            *path.rglob("*.ndjson"),
        ]
    )


def _validate_patient(patient: dict[str, Any], report: FileReport) -> None:
    # US Core 6.1 Patient required elements.
    identifiers = patient.get("identifier") or []
    if not identifiers:
        report.errors.append("Patient.identifier: US Core requires at least one identifier.")

    names = patient.get("name") or []
    if not names:
        report.errors.append("Patient.name: US Core requires at least one name.")
    else:
        first = names[0]
        if not first.get("family"):
            report.errors.append("Patient.name[0].family: US Core requires a family name.")

    if not patient.get("gender"):
        report.errors.append("Patient.gender: US Core requires gender.")

    # Atlas conventions — warn rather than fail so externally-sourced FHIR
    # still passes if a user ever runs validate on non-Atlas output.
    profiles = (patient.get("meta") or {}).get("profile") or []
    if US_CORE_PATIENT_PROFILE not in profiles:
        report.warnings.append(
            f"Patient.meta.profile does not claim {US_CORE_PATIENT_PROFILE}."
        )

    tags = (patient.get("meta") or {}).get("tag") or []
    if not any(t.get("code") == "HTEST" for t in tags):
        report.warnings.append("Patient.meta.tag missing HL7 HTEST synthetic-data marker.")

    ext_urls = {e.get("url") for e in patient.get("extension") or []}
    for required_ext in (US_CORE_RACE_URL, US_CORE_ETHNICITY_URL, US_CORE_BIRTHSEX_URL):
        if required_ext not in ext_urls:
            report.warnings.append(
                f"Patient.extension missing US Core extension: {required_ext}"
            )


def _validate_condition(condition: dict[str, Any], report: FileReport) -> None:
    # US Core Condition (Problems & Health Concerns) required elements.
    for required in ("clinicalStatus", "verificationStatus", "category", "code", "subject"):
        if not condition.get(required):
            report.errors.append(f"Condition.{required}: required by US Core.")


def _validate_medication_request(med: dict[str, Any], report: FileReport) -> None:
    # US Core MedicationRequest required elements.
    for required in ("status", "intent", "subject"):
        if not med.get(required):
            report.errors.append(f"MedicationRequest.{required}: required by US Core.")
    # medication is must-support and one of medicationCodeableConcept /
    # medicationReference must be present.
    if not (med.get("medicationCodeableConcept") or med.get("medicationReference")):
        report.errors.append(
            "MedicationRequest.medication[x]: required (CodeableConcept or Reference)."
        )
    if not med.get("authoredOn"):
        report.warnings.append(
            "MedicationRequest.authoredOn: must support per US Core."
        )


def _validate_encounter(encounter: dict[str, Any], report: FileReport) -> None:
    # US Core Encounter required elements.
    for required in ("identifier", "status", "class", "type", "subject"):
        if not encounter.get(required):
            report.errors.append(f"Encounter.{required}: required by US Core.")
    if not encounter.get("period"):
        report.warnings.append(
            "Encounter.period: must support per US Core (recommended)."
        )


def _validate_procedure(procedure: dict[str, Any], report: FileReport) -> None:
    # US Core Procedure required elements.
    for required in ("status", "code", "subject"):
        if not procedure.get(required):
            report.errors.append(f"Procedure.{required}: required by US Core.")
    # performed[x] is must-support per US Core.
    if not (
        procedure.get("performedDateTime")
        or procedure.get("performedPeriod")
        or procedure.get("performedString")
        or procedure.get("performedAge")
        or procedure.get("performedRange")
    ):
        report.warnings.append(
            "Procedure.performed[x]: must support per US Core (recommended)."
        )


def _validate_document_reference(doc: dict[str, Any], report: FileReport) -> None:
    # Base FHIR DocumentReference required elements (US Core conformance is
    # a future tightening; see the builder docstring).
    for required in ("status", "content", "subject"):
        if not doc.get(required):
            report.errors.append(
                f"DocumentReference.{required}: required by FHIR R4."
            )
    contents = doc.get("content") or []
    if contents and not any(
        (c.get("attachment") or {}).get("data") for c in contents
    ):
        report.warnings.append(
            "DocumentReference.content[].attachment.data: Atlas notes embed "
            "inline base64 content; missing data field."
        )


def _validate_observation(observation: dict[str, Any], report: FileReport) -> None:
    # US Core Observation required elements (shared across vital-signs,
    # blood-pressure, and lab-result profiles).
    for required in ("status", "category", "code", "subject"):
        if not observation.get(required):
            report.errors.append(f"Observation.{required}: required by US Core.")
    if not (
        observation.get("effectiveDateTime")
        or observation.get("effectivePeriod")
    ):
        report.errors.append(
            "Observation.effective[x]: required by US Core (dateTime or Period)."
        )
    # Must have a value OR components OR a dataAbsentReason.
    if not any(
        observation.get(k)
        for k in (
            "valueQuantity",
            "valueCodeableConcept",
            "valueString",
            "valueBoolean",
            "valueInteger",
            "valueRange",
            "valueRatio",
            "valueSampledData",
            "valueTime",
            "valueDateTime",
            "valuePeriod",
            "component",
            "dataAbsentReason",
        )
    ):
        report.errors.append(
            "Observation must carry value[x], component, or dataAbsentReason."
        )


def _validate_allergy(allergy: dict[str, Any], report: FileReport) -> None:
    for required in ("clinicalStatus", "verificationStatus", "code", "patient"):
        if not allergy.get(required):
            report.errors.append(f"AllergyIntolerance.{required}: required by US Core.")


def _validate_immunization(immunization: dict[str, Any], report: FileReport) -> None:
    for required in ("status", "vaccineCode", "patient"):
        if not immunization.get(required):
            report.errors.append(f"Immunization.{required}: required by US Core.")
    if not (
        immunization.get("occurrenceDateTime")
        or immunization.get("occurrenceString")
    ):
        report.errors.append("Immunization.occurrence[x]: required by FHIR R4.")


def _validate_diagnostic_report(report_resource: dict[str, Any], report: FileReport) -> None:
    for required in ("status", "code", "subject", "result"):
        if not report_resource.get(required):
            report.errors.append(f"DiagnosticReport.{required}: required by Atlas.")


def _validate_claim(claim: dict[str, Any], report: FileReport) -> None:
    for required in ("status", "type", "use", "patient", "created", "provider", "insurance", "item"):
        if not claim.get(required):
            report.errors.append(f"Claim.{required}: required by Atlas.")


def _validate_eob(eob: dict[str, Any], report: FileReport) -> None:
    for required in ("status", "type", "use", "patient", "created", "insurer", "provider", "outcome", "insurance", "item"):
        if not eob.get(required):
            report.errors.append(f"ExplanationOfBenefit.{required}: required by Atlas.")


def _validate_bundle(bundle: dict[str, Any], report: FileReport) -> None:
    try:
        _Bundle.model_validate(bundle)
    except Exception as exc:
        report.errors.append(f"Bundle schema validation failed: {exc}")
        return

    entries = bundle.get("entry") or []
    for i, entry in enumerate(entries):
        resource = entry.get("resource") or {}
        rtype = resource.get("resourceType")
        if rtype == "Patient":
            _validate_patient(resource, report)
        elif rtype == "Condition":
            _validate_condition(resource, report)
        elif rtype == "Observation":
            _validate_observation(resource, report)
        elif rtype == "Encounter":
            _validate_encounter(resource, report)
        elif rtype == "MedicationRequest":
            _validate_medication_request(resource, report)
        elif rtype == "DocumentReference":
            _validate_document_reference(resource, report)
        elif rtype == "Procedure":
            _validate_procedure(resource, report)
        elif rtype == "AllergyIntolerance":
            _validate_allergy(resource, report)
        elif rtype == "Immunization":
            _validate_immunization(resource, report)
        elif rtype == "DiagnosticReport":
            _validate_diagnostic_report(resource, report)
        elif rtype == "Claim":
            _validate_claim(resource, report)
        elif rtype == "ExplanationOfBenefit":
            _validate_eob(resource, report)
        elif rtype is None:
            report.errors.append(f"entry[{i}]: missing resourceType")
        else:
            # Other resource types aren't produced by Atlas yet. Schema is
            # still enforced via Bundle.model_validate above; skip reporting.
            pass


def _validate_resource_dict(
    resource: dict[str, Any], report: FileReport, *, context: str
) -> None:
    """Schema-validate a resource via fhir.resources, then run US Core checks."""
    rtype = resource.get("resourceType")
    if rtype is None:
        report.errors.append(f"{context}: missing resourceType")
        return
    cls = _FHIR_R4B_CLASSES.get(rtype)
    if cls is None:
        # Unknown / unsupported types pass silently in NDJSON mode — the
        # filename → type cross-check below will already have flagged any
        # mismatch.
        return
    try:
        cls.model_validate(resource)
    except Exception as exc:
        report.errors.append(f"{context}: schema validation failed: {exc}")
        return
    if rtype == "Patient":
        _validate_patient(resource, report)
    elif rtype == "Condition":
        _validate_condition(resource, report)
    elif rtype == "Observation":
        _validate_observation(resource, report)
    elif rtype == "Encounter":
        _validate_encounter(resource, report)
    elif rtype == "MedicationRequest":
        _validate_medication_request(resource, report)
    elif rtype == "DocumentReference":
        _validate_document_reference(resource, report)
    elif rtype == "Procedure":
        _validate_procedure(resource, report)
    elif rtype == "AllergyIntolerance":
        _validate_allergy(resource, report)
    elif rtype == "Immunization":
        _validate_immunization(resource, report)
    elif rtype == "DiagnosticReport":
        _validate_diagnostic_report(resource, report)
    elif rtype == "Claim":
        _validate_claim(resource, report)
    elif rtype == "ExplanationOfBenefit":
        _validate_eob(resource, report)


def _validate_ndjson_file(path: Path) -> FileReport:
    """Validate a `.ndjson` file: one resource per line, all of one resourceType.

    The file's resourceType is taken from the filename stem (Atlas writes
    `<ResourceType>.ndjson` in Bulk Data style). Each line is JSON-parsed,
    schema-validated, and run through the per-resource US Core checks.
    """
    report = FileReport(path=path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        report.errors.append(f"cannot read file: {exc}")
        return report

    expected_rtype = path.stem
    if expected_rtype not in _FHIR_R4B_CLASSES:
        report.warnings.append(
            f"NDJSON filename stem {expected_rtype!r} is not a recognized Atlas "
            f"resourceType ({sorted(_FHIR_R4B_CLASSES)}); per-line validation "
            f"will skip the schema check."
        )
        expected_rtype = None  # disable cross-check

    line_count = 0
    for lineno, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        line_count += 1
        try:
            resource = json.loads(line)
        except json.JSONDecodeError as exc:
            report.errors.append(f"line {lineno}: invalid JSON: {exc}")
            continue
        actual_rtype = resource.get("resourceType")
        if expected_rtype and actual_rtype != expected_rtype:
            report.errors.append(
                f"line {lineno}: resourceType {actual_rtype!r} doesn't match "
                f"filename {path.name!r} (expected {expected_rtype!r})"
            )
            # Continue to schema-validate anyway so the user sees other errors.
        _validate_resource_dict(resource, report, context=f"line {lineno}")

    if line_count == 0:
        report.warnings.append("ndjson file has no data lines")
    return report


def validate_file(path: Path) -> FileReport:
    """Validate a single FHIR file (JSON Bundle / Patient, or NDJSON)."""
    if path.suffix == ".ndjson":
        return _validate_ndjson_file(path)
    report = FileReport(path=path)
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        report.errors.append(f"cannot read/parse JSON: {exc}")
        return report

    rtype = data.get("resourceType")
    if rtype == "Bundle":
        _validate_bundle(data, report)
    elif rtype == "Patient":
        _validate_patient(data, report)
    else:
        report.errors.append(
            f"top-level resourceType {rtype!r} — expected Bundle or Patient"
        )
    return report


def validate_path(path: Path) -> ValidationSummary:
    """Validate every JSON / NDJSON file at or beneath `path`."""
    summary = ValidationSummary()
    for f in _iter_json_files(path):
        summary.files.append(validate_file(f))
    return summary

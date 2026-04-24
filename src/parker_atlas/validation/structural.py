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

from parker_atlas.fhir.patient import (
    US_CORE_BIRTHSEX_URL,
    US_CORE_ETHNICITY_URL,
    US_CORE_PATIENT_PROFILE,
    US_CORE_RACE_URL,
)


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
    if path.is_file():
        return [path]
    return sorted(path.rglob("*.json"))


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
        elif rtype is None:
            report.errors.append(f"entry[{i}]: missing resourceType")
        else:
            # Other resource types aren't produced by Atlas yet. Schema is
            # still enforced via Bundle.model_validate above; skip reporting.
            pass


def validate_file(path: Path) -> FileReport:
    """Validate a single JSON file and return a per-file report."""
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
    """Validate every JSON file at or beneath `path`."""
    summary = ValidationSummary()
    for f in _iter_json_files(path):
        summary.files.append(validate_file(f))
    return summary

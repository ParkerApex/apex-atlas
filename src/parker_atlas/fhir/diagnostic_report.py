"""
FHIR R4 DiagnosticReport construction.

DiagnosticReport groups related Observations such as a lipid panel, CBC,
or BMP under one clinical report, with optional narrative conclusion.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from fhir.resources.R4B.diagnosticreport import DiagnosticReport as _DiagnosticReport

from parker_atlas.fhir._datetime import fhir_datetime
from parker_atlas.gpx import GPX
from parker_atlas.modules.runtime import Coding

US_CORE_DIAGNOSTIC_REPORT_LAB_PROFILE = (
    "http://hl7.org/fhir/us/core/StructureDefinition/us-core-diagnosticreport-lab|6.1.0"
)
DIAGNOSTIC_SERVICE_SECTION_SYSTEM = (
    "http://terminology.hl7.org/CodeSystem/v2-0074"
)
PARKER_DIAGNOSTIC_REPORT_IDENTIFIER_SYSTEM = (
    "https://parkerapex.com/atlas/diagnostic-report"
)

_URL_NAMESPACE = uuid.UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8")


def diagnostic_report_id(gpx: GPX, report_spec_id: str) -> str:
    """Deterministic DiagnosticReport.id derived from GPX + spec id."""
    return str(uuid.uuid5(_URL_NAMESPACE, f"{gpx}:diagnostic-report:{report_spec_id}"))


def build_diagnostic_report_resource(
    gpx: GPX,
    patient_fullurl: str,
    report_spec_id: str,
    *,
    code: Coding,
    effective: date | datetime,
    result_fullurls: tuple[str, ...],
    conclusion: str | None = None,
    status: str = "final",
    encounter_fullurl: str | None = None,
    category_code: str = "LAB",
    category_display: str = "Laboratory",
) -> dict[str, Any]:
    """Build a lab DiagnosticReport referencing related Observations."""
    rid = diagnostic_report_id(gpx, report_spec_id)
    resource: dict[str, Any] = {
        "resourceType": "DiagnosticReport",
        "id": rid,
        "meta": {
            "profile": [US_CORE_DIAGNOSTIC_REPORT_LAB_PROFILE],
            "tag": [GPX.synthetic_meta_tag()],
        },
        "identifier": [
            {
                "system": PARKER_DIAGNOSTIC_REPORT_IDENTIFIER_SYSTEM,
                "value": rid,
            }
        ],
        "status": status,
        "category": [
            {
                "coding": [
                    {
                        "system": DIAGNOSTIC_SERVICE_SECTION_SYSTEM,
                        "code": category_code,
                        "display": category_display,
                    }
                ],
                "text": category_display,
            }
        ],
        "code": {
            "coding": [
                {
                    "system": code.system,
                    "code": code.code,
                    "display": code.display,
                }
            ],
            "text": code.display,
        },
        "subject": {"reference": patient_fullurl},
        "effectiveDateTime": fhir_datetime(effective),
        "result": [{"reference": ref} for ref in result_fullurls],
    }
    if conclusion is not None:
        resource["conclusion"] = conclusion
    if encounter_fullurl is not None:
        resource["encounter"] = {"reference": encounter_fullurl}

    _DiagnosticReport.model_validate(resource)
    return resource

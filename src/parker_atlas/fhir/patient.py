"""
FHIR R4 Patient resource construction with US Core 6.1 conformance.

Produces a dict-shaped Patient resource that round-trips through the
`fhir.resources.R4B.patient.Patient` pydantic model. The resource carries:

- Parker GPX as an Identifier
- US Core race, ethnicity, and birthsex extensions
- HL7 HTEST meta.tag to mark the data as synthetic
- meta.profile claim of US Core 6.1 Patient conformance
"""

from __future__ import annotations

from datetime import date
from typing import Any

from fhir.resources.R4B.patient import Patient as _Patient

from parker_atlas.core.demographics import (
    AdministrativeGender,
    Demographics,
    ethnicity_display,
    race_display,
)
from parker_atlas.gpx import GPX

US_CORE_PATIENT_PROFILE = (
    "http://hl7.org/fhir/us/core/StructureDefinition/us-core-patient|6.1.0"
)
OMB_RACE_CODE_SYSTEM = "urn:oid:2.16.840.1.113883.6.238"
US_CORE_RACE_URL = "http://hl7.org/fhir/us/core/StructureDefinition/us-core-race"
US_CORE_ETHNICITY_URL = "http://hl7.org/fhir/us/core/StructureDefinition/us-core-ethnicity"
US_CORE_BIRTHSEX_URL = "http://hl7.org/fhir/us/core/StructureDefinition/us-core-birthsex"


def _race_extension(demo: Demographics) -> dict[str, Any]:
    display = race_display(demo.race)
    return {
        "url": US_CORE_RACE_URL,
        "extension": [
            {
                "url": "ombCategory",
                "valueCoding": {
                    "system": OMB_RACE_CODE_SYSTEM,
                    "code": demo.race.value,
                    "display": display,
                },
            },
            {"url": "text", "valueString": display},
        ],
    }


def _ethnicity_extension(demo: Demographics) -> dict[str, Any]:
    display = ethnicity_display(demo.ethnicity)
    return {
        "url": US_CORE_ETHNICITY_URL,
        "extension": [
            {
                "url": "ombCategory",
                "valueCoding": {
                    "system": OMB_RACE_CODE_SYSTEM,
                    "code": demo.ethnicity.value,
                    "display": display,
                },
            },
            {"url": "text", "valueString": display},
        ],
    }


def _birthsex_extension(demo: Demographics) -> dict[str, Any]:
    code = "F" if demo.birth_sex is AdministrativeGender.FEMALE else "M"
    return {"url": US_CORE_BIRTHSEX_URL, "valueCode": code}


def build_patient_resource(
    gpx: GPX,
    demo: Demographics,
    *,
    deceased_date: date | None = None,
) -> dict[str, Any]:
    """Build a US Core 6.1-conformant Patient resource as a JSON-ready dict.

    The returned dict is validated against the fhir.resources R4B Patient model
    before being returned, so any schema drift fails loudly at construction time
    rather than at ingestion.
    """
    resource: dict[str, Any] = {
        "resourceType": "Patient",
        "id": str(gpx),
        "meta": {
            "profile": [US_CORE_PATIENT_PROFILE],
            "tag": [GPX.synthetic_meta_tag()],
        },
        "extension": [
            _race_extension(demo),
            _ethnicity_extension(demo),
            _birthsex_extension(demo),
        ],
        "identifier": [gpx.to_fhir_identifier()],
        "name": [
            {
                "use": "official",
                "family": demo.family_name,
                "given": [demo.given_name],
            }
        ],
        "gender": demo.gender.value,
        "birthDate": demo.birth_date.isoformat(),
    }

    if deceased_date is not None:
        resource["deceasedDateTime"] = deceased_date.isoformat()

    _Patient.model_validate(resource)
    return resource

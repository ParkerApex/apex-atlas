"""
FHIR R4 Observation resources for Social Determinants of Health (SDoH).

Uses Gravity Project / SDOHCC codes (LOINC screening questions + SNOMED
answers) to represent each SDoH risk domain as a structured Observation.
These are the codes used by Epic, Cerner, and major EHRs for SDoH capture,
making Atlas-generated data immediately compatible with real-world
integration targets.

FHIR profile: SDOHCC Observation Screening Response
(http://hl7.org/fhir/us/sdoh-clinicalcare/StructureDefinition/SDOHCC-ObservationScreeningResponse)

For each domain we emit:
- `code`:  The LOINC screening question code for the domain
- `valueCodeableConcept`: A LOINC answer code (presence/absence)
- `category`: social-history + the SDOHCC screening-domain category

Codes are drawn from:
- LOINC Gravity Project panels (88122-0, 88123-8, etc.)
- SDOHCC CodeSystem for category tagging
- HL7 VSAC value sets for answers
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from parker_atlas.core.sdoh import SDoHProfile
from parker_atlas.fhir._datetime import fhir_datetime
from parker_atlas.gpx import GPX

_URL_NAMESPACE = uuid.UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8")

SDOHCC_PROFILE = (
    "http://hl7.org/fhir/us/sdoh-clinicalcare/StructureDefinition/"
    "SDOHCC-ObservationScreeningResponse"
)

_SDOHCC_CATEGORY_SYSTEM = (
    "http://hl7.org/fhir/us/sdoh-clinicalcare/CodeSystem/SDOHCC-CodeSystemTemporaryCodes"
)
_OBS_CATEGORY_SYSTEM = (
    "http://terminology.hl7.org/CodeSystem/observation-category"
)
_LOINC = "http://loinc.org"
_SNOMED = "http://snomed.info/sct"

# Gravity Project LOINC codes — screener questions and answer value sets.
# Each tuple: (question_loinc, question_display, sdohcc_category_code,
#              sdohcc_category_display,
#              positive_answer_loinc, positive_answer_display,
#              negative_answer_loinc, negative_answer_display)
_DOMAIN_CODES: dict[str, tuple[str, str, str, str, str, str, str, str]] = {
    "food_insecurity": (
        "88122-0",
        "Within the past 12 months, we worried whether our food would run out",
        "food-insecurity",
        "Food Insecurity",
        "LA33-6",  "Yes",
        "LA32-8",  "No",
    ),
    "housing_instability": (
        "71802-3",
        "What is your living situation today?",
        "housing-instability",
        "Housing Instability",
        "LA31996-4", "I have a place to live today, but I am worried about losing it in the future",
        "LA31994-9", "I have housing",
    ),
    "transportation_barrier": (
        "93030-5",
        "Has lack of transportation kept you from medical appointments, meetings, work, or from getting things needed for daily living?",
        "transportation-insecurity",
        "Transportation Insecurity",
        "LA33-6",  "Yes",
        "LA32-8",  "No",
    ),
    "financial_strain": (
        "96780-2",
        "Do you want help finding or keeping work or a job?",
        "financial-insecurity",
        "Financial Insecurity",
        "LA33-6",  "Yes, help finding work",
        "LA32-8",  "No",
    ),
    "inadequate_social_support": (
        "54899-0",
        "How often do you feel lonely or isolated from those around you?",
        "social-connection",
        "Social Connection",
        "LA6270-8", "Never",   # counterintuitively: high loneliness → positive screen
        "LA10066-1", "Rarely",
    ),
}


def _obs_id(gpx: GPX, domain: str) -> str:
    return str(uuid.uuid5(_URL_NAMESPACE, f"{gpx}:sdoh:{domain}"))


def build_sdoh_observation(
    gpx: GPX,
    patient_fullurl: str,
    domain: str,
    positive: bool,
    effective: date | datetime,
) -> dict[str, Any]:
    """Build one SDOHCC Observation for a single SDoH domain.

    Args:
        gpx: patient GPX identifier.
        patient_fullurl: Bundle fullUrl for the Patient resource.
        domain: one of the keys in `_DOMAIN_CODES`.
        positive: True if the risk factor is present for this patient.
        effective: date of the screening (typically today).

    Returns:
        A FHIR R4 Observation dict conforming to the SDOHCC Screening
        Response profile.
    """
    if domain not in _DOMAIN_CODES:
        raise ValueError(
            f"unknown SDoH domain {domain!r}; choices: {sorted(_DOMAIN_CODES)}"
        )
    q_loinc, q_display, cat_code, cat_display, pos_code, pos_display, neg_code, neg_display = (
        _DOMAIN_CODES[domain]
    )
    answer_code = pos_code if positive else neg_code
    answer_display = pos_display if positive else neg_display

    return {
        "resourceType": "Observation",
        "id": _obs_id(gpx, domain),
        "meta": {
            "profile": [SDOHCC_PROFILE],
            "tag": [GPX.synthetic_meta_tag()],
        },
        "status": "final",
        "category": [
            {
                "coding": [
                    {
                        "system": _OBS_CATEGORY_SYSTEM,
                        "code": "social-history",
                        "display": "Social History",
                    }
                ]
            },
            {
                "coding": [
                    {
                        "system": _SDOHCC_CATEGORY_SYSTEM,
                        "code": cat_code,
                        "display": cat_display,
                    }
                ]
            },
        ],
        "code": {
            "coding": [{"system": _LOINC, "code": q_loinc, "display": q_display}],
            "text": q_display,
        },
        "subject": {"reference": patient_fullurl},
        "effectiveDateTime": fhir_datetime(effective),
        "valueCodeableConcept": {
            "coding": [{"system": _LOINC, "code": answer_code, "display": answer_display}],
            "text": answer_display,
        },
    }


def build_sdoh_observations(
    gpx: GPX,
    patient_fullurl: str,
    profile: SDoHProfile,
    effective: date | datetime,
) -> list[dict[str, Any]]:
    """Build all five SDOHCC Observations for a patient's SDoH profile.

    Always emits all five domains (positive AND negative screens) so
    that downstream analytics can distinguish "screened negative" from
    "never screened." This is consistent with AHC HRSN screenings in
    Medicare.

    Args:
        gpx: patient GPX identifier.
        patient_fullurl: Bundle fullUrl for the Patient resource.
        profile: sampled SDoH profile from `sample_sdoh`.
        effective: date of the screening.
    """
    return [
        build_sdoh_observation(
            gpx=gpx,
            patient_fullurl=patient_fullurl,
            domain="food_insecurity",
            positive=profile.food_insecurity,
            effective=effective,
        ),
        build_sdoh_observation(
            gpx=gpx,
            patient_fullurl=patient_fullurl,
            domain="housing_instability",
            positive=profile.housing_instability,
            effective=effective,
        ),
        build_sdoh_observation(
            gpx=gpx,
            patient_fullurl=patient_fullurl,
            domain="transportation_barrier",
            positive=profile.transportation_barrier,
            effective=effective,
        ),
        build_sdoh_observation(
            gpx=gpx,
            patient_fullurl=patient_fullurl,
            domain="financial_strain",
            positive=profile.financial_strain,
            effective=effective,
        ),
        build_sdoh_observation(
            gpx=gpx,
            patient_fullurl=patient_fullurl,
            domain="inadequate_social_support",
            positive=profile.inadequate_social_support,
            effective=effective,
        ),
    ]

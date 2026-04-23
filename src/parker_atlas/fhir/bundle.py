"""
FHIR R4 Bundle assembly.

Milestone 1 produces one transaction Bundle per patient, each containing
only the Patient resource. Clinical resources (Encounter, Condition,
Observation, MedicationRequest) land in Milestone 2 and will be added to
the same Bundle.
"""

from __future__ import annotations

import uuid
from typing import Any

from fhir.resources.R4B.bundle import Bundle as _Bundle

from parker_atlas.gpx import GPX

# URL namespace UUID (RFC 4122) — used to mint stable UUID5 fullUrls from GPX strings.
_URL_NAMESPACE = uuid.UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8")


def fullurl_for_gpx(gpx: GPX) -> str:
    """Return a deterministic urn:uuid fullUrl for a given GPX identifier."""
    return f"urn:uuid:{uuid.uuid5(_URL_NAMESPACE, str(gpx))}"


def patient_bundle(gpx: GPX, patient_resource: dict[str, Any]) -> dict[str, Any]:
    """Wrap a Patient resource in a single-entry transaction Bundle."""
    bundle: dict[str, Any] = {
        "resourceType": "Bundle",
        "type": "transaction",
        "entry": [
            {
                "fullUrl": fullurl_for_gpx(gpx),
                "resource": patient_resource,
                "request": {"method": "POST", "url": "Patient"},
            }
        ],
    }
    _Bundle.model_validate(bundle)
    return bundle

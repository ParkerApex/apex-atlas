"""
FHIR R4 Bundle assembly.

Builds transaction Bundles that carry the Patient and any module-emitted
clinical resources (Condition, and later Encounter / Observation /
MedicationRequest). fullUrls are deterministic `urn:uuid` values derived
from the patient's GPX, so a given seed always produces byte-identical
Bundles.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any

from fhir.resources.R4B.bundle import Bundle as _Bundle

from parker_atlas.gpx import GPX

# URL namespace UUID (RFC 4122) — used to mint stable UUID5 fullUrls from GPX strings.
_URL_NAMESPACE = uuid.UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8")


def fullurl_for_gpx(gpx: GPX) -> str:
    """Return a deterministic urn:uuid fullUrl for a patient's Bundle entry."""
    return f"urn:uuid:{uuid.uuid5(_URL_NAMESPACE, str(gpx))}"


def fullurl_for_resource(gpx: GPX, resource: dict[str, Any]) -> str:
    """Return a deterministic urn:uuid fullUrl for a non-Patient resource.

    The URL is derived from the patient GPX + resourceType + resource id, so it
    is stable across runs given the same seed and also collision-free within a
    single patient's Bundle.
    """
    key = f"{gpx}:{resource['resourceType']}:{resource.get('id', '')}"
    return f"urn:uuid:{uuid.uuid5(_URL_NAMESPACE, key)}"


def _entry(full_url: str, resource: dict[str, Any]) -> dict[str, Any]:
    return {
        "fullUrl": full_url,
        "resource": resource,
        "request": {"method": "POST", "url": resource["resourceType"]},
    }


def build_bundle(
    gpx: GPX,
    patient_resource: dict[str, Any],
    extras: Sequence[dict[str, Any]] = (),
) -> dict[str, Any]:
    """Build a transaction Bundle with a Patient and any extra resources.

    `extras` are module-emitted resources (Condition, Encounter, etc.) that
    already carry references to the Patient's fullUrl.
    """
    entries = [_entry(fullurl_for_gpx(gpx), patient_resource)]
    for res in extras:
        entries.append(_entry(fullurl_for_resource(gpx, res), res))

    bundle: dict[str, Any] = {
        "resourceType": "Bundle",
        "type": "transaction",
        "entry": entries,
    }
    _Bundle.model_validate(bundle)
    return bundle


def patient_bundle(gpx: GPX, patient_resource: dict[str, Any]) -> dict[str, Any]:
    """Build a single-Patient transaction Bundle (back-compat thin wrapper)."""
    return build_bundle(gpx, patient_resource)

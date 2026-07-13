"""
FHIR R4 builders for the Da Vinci PDEX Plan-Net provider directory.

Plan-Net (http://hl7.org/fhir/us/davinci-pdex-plan-net/) is the Da Vinci
implementation guide for payer provider directories — the resources a health
plan publishes so members (and CMS Interoperability rule consumers) can find
in-network providers, locations, networks, and plans.

These builders emit the Plan-Net-profiled resources with relative references
(``Organization/<id>`` etc.), suitable for a bulk NDJSON directory export.
Everything is synthetic and carries the HTEST tag.
"""

from __future__ import annotations

import uuid
from typing import Any

from fhir.resources.R4B.endpoint import Endpoint as _Endpoint
from fhir.resources.R4B.healthcareservice import HealthcareService as _HealthcareService
from fhir.resources.R4B.insuranceplan import InsurancePlan as _InsurancePlan
from fhir.resources.R4B.location import Location as _Location
from fhir.resources.R4B.organization import Organization as _Organization
from fhir.resources.R4B.practitioner import Practitioner as _Practitioner
from fhir.resources.R4B.practitionerrole import PractitionerRole as _PractitionerRole

from parker_atlas.gpx import GPX

_BASE = "http://hl7.org/fhir/us/davinci-pdex-plan-net/StructureDefinition"
PLANNET_ORGANIZATION = f"{_BASE}/plannet-Organization"
PLANNET_NETWORK = f"{_BASE}/plannet-Network"
PLANNET_LOCATION = f"{_BASE}/plannet-Location"
PLANNET_PRACTITIONER = f"{_BASE}/plannet-Practitioner"
PLANNET_PRACTITIONER_ROLE = f"{_BASE}/plannet-PractitionerRole"
PLANNET_HEALTHCARE_SERVICE = f"{_BASE}/plannet-HealthcareService"
PLANNET_INSURANCE_PLAN = f"{_BASE}/plannet-InsurancePlan"
PLANNET_ENDPOINT = f"{_BASE}/plannet-Endpoint"
NETWORK_REFERENCE_EXT = f"{_BASE}/network-reference"
NEWPATIENTS_EXT = f"{_BASE}/newpatients"

NUCC_SYSTEM = "http://nucc.org/provider-taxonomy"
US_NPI_SYSTEM = "http://hl7.org/fhir/sid/us-npi"
ORG_TYPE_SYSTEM = "http://terminology.hl7.org/CodeSystem/organization-type"
HEALTHCARE_SERVICE_CATEGORY = "http://terminology.hl7.org/CodeSystem/service-category"
HEALTHCARE_SERVICE_TYPE = "http://terminology.hl7.org/CodeSystem/service-type"
NEWPATIENT_SYSTEM = "http://hl7.org/fhir/us/davinci-pdex-plan-net/CodeSystem/AcceptingPatientsCS"

_NS = uuid.UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8")


def _id(*parts: str) -> str:
    return str(uuid.uuid5(_NS, "plannet:" + ":".join(parts)))


def _meta(profile: str) -> dict[str, Any]:
    return {"profile": [profile], "tag": [GPX.synthetic_meta_tag()]}


def location_id_for(org_npi: str, name: str) -> str:
    """Deterministic Plan-Net Location.id for (facility NPI, location name)."""
    return _id("location", org_npi, name)


def build_network(*, network_key: str, name: str) -> dict[str, Any]:
    """A Plan-Net Network (Organization with type=ntwk)."""
    resource = {
        "resourceType": "Organization",
        "id": _id("network", network_key),
        "meta": _meta(PLANNET_NETWORK),
        "active": True,
        "type": [
            {"coding": [{"system": ORG_TYPE_SYSTEM, "code": "ntwk", "display": "Network"}]}
        ],
        "name": name,
    }
    _Organization.model_validate(resource)
    return resource


def build_organization(*, npi: str, name: str) -> dict[str, Any]:
    """A Plan-Net provider Organization (a facility/practice)."""
    resource = {
        "resourceType": "Organization",
        "id": _id("org", npi),
        "meta": _meta(PLANNET_ORGANIZATION),
        "identifier": [{"system": US_NPI_SYSTEM, "value": npi}],
        "active": True,
        "type": [
            {"coding": [{"system": ORG_TYPE_SYSTEM, "code": "prov", "display": "Healthcare Provider"}]}
        ],
        "name": name,
    }
    _Organization.model_validate(resource)
    return resource


def build_location(
    *,
    org_npi: str,
    name: str,
    line: str,
    city: str,
    state: str,
    postal_code: str,
    latitude: float | None = None,
    longitude: float | None = None,
    phone: str | None = None,
) -> dict[str, Any]:
    """A Plan-Net Location managed by a provider Organization."""
    resource: dict[str, Any] = {
        "resourceType": "Location",
        "id": _id("location", org_npi, name),
        "meta": _meta(PLANNET_LOCATION),
        "status": "active",
        "name": name,
        "address": {
            "use": "work",
            "line": [line],
            "city": city,
            "state": state,
            "postalCode": postal_code,
            "country": "US",
        },
        "managingOrganization": {"reference": f"Organization/{_id('org', org_npi)}"},
    }
    if latitude is not None and longitude is not None:
        resource["position"] = {"latitude": latitude, "longitude": longitude}
    if phone is not None:
        resource["telecom"] = [{"system": "phone", "value": phone, "use": "work"}]
    _Location.model_validate(resource)
    return resource


def build_practitioner(
    *, npi: str, family: str, given: str, prefix: str, taxonomy_code: str, taxonomy_display: str
) -> dict[str, Any]:
    """A Plan-Net Practitioner with an NPI and a board qualification."""
    name: dict[str, Any] = {"family": family, "given": [given]}
    if prefix:
        name["prefix"] = [prefix]
    resource = {
        "resourceType": "Practitioner",
        "id": _id("practitioner", npi),
        "meta": _meta(PLANNET_PRACTITIONER),
        "identifier": [{"system": US_NPI_SYSTEM, "value": npi}],
        "active": True,
        "name": [name],
        "qualification": [
            {
                "code": {
                    "coding": [
                        {"system": NUCC_SYSTEM, "code": taxonomy_code, "display": taxonomy_display}
                    ],
                    "text": taxonomy_display,
                }
            }
        ],
    }
    _Practitioner.model_validate(resource)
    return resource


def build_healthcare_service(
    *, org_npi: str, location_id: str, service_key: str, category_code: str,
    category_display: str, type_code: str, type_display: str,
) -> dict[str, Any]:
    """A Plan-Net HealthcareService offered by an Organization at a Location."""
    resource = {
        "resourceType": "HealthcareService",
        "id": _id("service", org_npi, service_key),
        "meta": _meta(PLANNET_HEALTHCARE_SERVICE),
        "active": True,
        "providedBy": {"reference": f"Organization/{_id('org', org_npi)}"},
        "category": [
            {"coding": [{"system": HEALTHCARE_SERVICE_CATEGORY, "code": category_code, "display": category_display}]}
        ],
        "type": [
            {"coding": [{"system": HEALTHCARE_SERVICE_TYPE, "code": type_code, "display": type_display}]}
        ],
        "location": [{"reference": f"Location/{location_id}"}],
    }
    _HealthcareService.model_validate(resource)
    return resource


def build_practitioner_role(
    *,
    practitioner_id: str,
    org_id: str,
    location_id: str,
    service_id: str,
    network_id: str,
    role_code: str,
    role_display: str,
    specialty_code: str,
    specialty_display: str,
    accepting_new_patients: bool = True,
) -> dict[str, Any]:
    """A Plan-Net PractitionerRole tying a practitioner to org/location/network."""
    role_key = f"{practitioner_id}:{org_id}:{specialty_code}"
    accept = "newpt" if accepting_new_patients else "nopt"
    resource = {
        "resourceType": "PractitionerRole",
        "id": _id("role", role_key),
        "meta": _meta(PLANNET_PRACTITIONER_ROLE),
        "extension": [
            {
                "url": NETWORK_REFERENCE_EXT,
                "valueReference": {"reference": f"Organization/{network_id}"},
            }
        ],
        "active": True,
        "practitioner": {"reference": f"Practitioner/{practitioner_id}"},
        "organization": {"reference": f"Organization/{org_id}"},
        "code": [
            {"coding": [{"system": NUCC_SYSTEM, "code": role_code, "display": role_display}]}
        ],
        "specialty": [
            {
                "coding": [{"system": NUCC_SYSTEM, "code": specialty_code, "display": specialty_display}],
                "extension": [
                    {
                        "url": NEWPATIENTS_EXT,
                        "extension": [
                            {
                                "url": "acceptingPatients",
                                "valueCodeableConcept": {
                                    "coding": [
                                        {
                                            "system": NEWPATIENT_SYSTEM,
                                            "code": accept,
                                            "display": "Accepting" if accepting_new_patients else "Not Accepting",
                                        }
                                    ]
                                },
                            }
                        ],
                    }
                ],
            }
        ],
        "location": [{"reference": f"Location/{location_id}"}],
        "healthcareService": [{"reference": f"HealthcareService/{service_id}"}],
    }
    _PractitionerRole.model_validate(resource)
    return resource


def build_insurance_plan(
    *, plan_key: str, name: str, plan_type_code: str, plan_type_display: str,
    owned_by_org_id: str, network_ids: list[str],
) -> dict[str, Any]:
    """A Plan-Net InsurancePlan referencing its network(s)."""
    resource = {
        "resourceType": "InsurancePlan",
        "id": _id("plan", plan_key),
        "meta": _meta(PLANNET_INSURANCE_PLAN),
        "status": "active",
        # Text-only product type (PPO/HMO) — avoids asserting a specific
        # standard code system for synthetic data.
        "type": [{"text": plan_type_display}],
        "name": name,
        "ownedBy": {"reference": f"Organization/{owned_by_org_id}"},
        "network": [{"reference": f"Organization/{nid}"} for nid in network_ids],
    }
    _InsurancePlan.model_validate(resource)
    return resource


def build_endpoint(*, org_npi: str, org_id: str, base_url: str) -> dict[str, Any]:
    """A Plan-Net Endpoint (a FHIR base URL) for an Organization."""
    resource = {
        "resourceType": "Endpoint",
        "id": _id("endpoint", org_npi),
        "meta": _meta(PLANNET_ENDPOINT),
        "status": "active",
        "connectionType": {
            "system": "http://terminology.hl7.org/CodeSystem/endpoint-connection-type",
            "code": "hl7-fhir-rest",
            "display": "HL7 FHIR",
        },
        "managingOrganization": {"reference": f"Organization/{org_id}"},
        "payloadType": [
            {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/endpoint-payload-type", "code": "any", "display": "Any"}]}
        ],
        "address": base_url,
    }
    _Endpoint.model_validate(resource)
    return resource

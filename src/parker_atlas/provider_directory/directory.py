"""
Da Vinci PDEX Plan-Net provider directory generation.

Builds a synthetic payer provider directory — Networks, provider Organizations,
Locations, Practitioners, PractitionerRoles, HealthcareServices, InsurancePlans,
and Endpoints — conforming to the Plan-Net profiles. Serialization to a bulk
NDJSON directory + manifest lives in :mod:`parker_atlas.provider_directory.publish`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from parker_atlas.fhir import plannet
from parker_atlas.scheduling.links import CLINIC_SITES

SERVICE_CATEGORY_CODE = "17"
SERVICE_CATEGORY_DISPLAY = "General Practice"


@dataclass(frozen=True, slots=True)
class Specialty:
    taxonomy_code: str      # NUCC provider taxonomy
    display: str


# NUCC provider-taxonomy specialties.
SPECIALTIES: tuple[Specialty, ...] = (
    Specialty("207Q00000X", "Family Medicine"),
    Specialty("207R00000X", "Internal Medicine"),
    Specialty("207RC0000X", "Cardiovascular Disease"),
    Specialty("208000000X", "Pediatrics"),
    Specialty("207V00000X", "Obstetrics & Gynecology"),
    Specialty("2084N0400X", "Neurology"),
)

_GIVEN = ("Ava", "Liam", "Maria", "Noah", "Priya", "Diego", "Grace", "Omar", "Chloe", "Ravi")
_FAMILY = ("Nguyen", "Patel", "Garcia", "Kim", "Johnson", "Okafor", "Rossi", "Cohen", "Silva", "Adams")

# Two networks the directory advertises.
NETWORKS = (
    ("ppo", "Apex Choice PPO Network", "PPO"),
    ("hmo", "Apex Care HMO Network", "HMO"),
)


@dataclass(slots=True)
class DirectoryConfig:
    sites: int = 15
    practitioners_per_site: int = 4

    def validate(self) -> None:
        if not 1 <= self.sites <= len(CLINIC_SITES):
            raise ValueError(f"sites must be between 1 and {len(CLINIC_SITES)}")
        if self.practitioners_per_site < 1:
            raise ValueError("practitioners_per_site must be >= 1")


@dataclass(slots=True)
class ProviderDirectory:
    organizations: list[dict] = field(default_factory=list)  # networks + providers
    locations: list[dict] = field(default_factory=list)
    practitioners: list[dict] = field(default_factory=list)
    practitioner_roles: list[dict] = field(default_factory=list)
    healthcare_services: list[dict] = field(default_factory=list)
    insurance_plans: list[dict] = field(default_factory=list)
    endpoints: list[dict] = field(default_factory=list)

    @property
    def counts(self) -> dict[str, int]:
        return {
            "Organization": len(self.organizations),
            "Location": len(self.locations),
            "Practitioner": len(self.practitioners),
            "PractitionerRole": len(self.practitioner_roles),
            "HealthcareService": len(self.healthcare_services),
            "InsurancePlan": len(self.insurance_plans),
            "Endpoint": len(self.endpoints),
        }


def generate_provider_directory(config: DirectoryConfig) -> ProviderDirectory:
    """Generate a Plan-Net provider directory from ``config`` (deterministic)."""
    config.validate()
    directory = ProviderDirectory()

    networks = [plannet.build_network(network_key=k, name=n) for k, n, _ in NETWORKS]
    network_ids = [n["id"] for n in networks]
    directory.organizations.extend(networks)

    seen_services: set[str] = set()
    practitioner_counter = 0

    for idx, site in enumerate(CLINIC_SITES[: config.sites]):
        org_npi = f"{8000000000 + idx:010d}"
        org = plannet.build_organization(
            npi=org_npi, name=f"Apex Atlas Medical Group — {site.city}"
        )
        directory.organizations.append(org)
        org_id = org["id"]

        location = plannet.build_location(
            org_npi=org_npi,
            name=f"{site.city} Clinic",
            line=f"{200 + idx} Medical Center Dr",
            city=site.city,
            state=site.state,
            postal_code=f"{20000 + idx * 41:05d}",
            latitude=site.latitude,
            longitude=site.longitude,
            phone=f"1-800-555-{4000 + idx:04d}",
        )
        directory.locations.append(location)
        loc_id = location["id"]

        directory.endpoints.append(
            plannet.build_endpoint(
                org_npi=org_npi, org_id=org_id,
                base_url=f"https://fhir.example.org/plannet/{org_npi}",
            )
        )

        for _ in range(config.practitioners_per_site):
            spec = SPECIALTIES[practitioner_counter % len(SPECIALTIES)]
            prac_npi = f"{7000000000 + practitioner_counter:010d}"
            given = _GIVEN[practitioner_counter % len(_GIVEN)]
            family = _FAMILY[(practitioner_counter // len(_GIVEN)) % len(_FAMILY)]
            practitioner = plannet.build_practitioner(
                npi=prac_npi, family=family, given=given, prefix="Dr.",
                taxonomy_code=spec.taxonomy_code, taxonomy_display=spec.display,
            )
            directory.practitioners.append(practitioner)
            prac_id = practitioner["id"]

            service = plannet.build_healthcare_service(
                org_npi=org_npi, location_id=loc_id, service_key=spec.taxonomy_code,
                category_code=SERVICE_CATEGORY_CODE, category_display=SERVICE_CATEGORY_DISPLAY,
                type_code=spec.taxonomy_code, type_display=spec.display,
            )
            if service["id"] not in seen_services:
                seen_services.add(service["id"])
                directory.healthcare_services.append(service)

            network_id = network_ids[practitioner_counter % len(network_ids)]
            role = plannet.build_practitioner_role(
                practitioner_id=prac_id, org_id=org_id, location_id=loc_id,
                service_id=service["id"], network_id=network_id,
                role_code=spec.taxonomy_code, role_display=spec.display,
                specialty_code=spec.taxonomy_code, specialty_display=spec.display,
                accepting_new_patients=(practitioner_counter % 4 != 0),
            )
            directory.practitioner_roles.append(role)
            practitioner_counter += 1

    owner_org_id = directory.organizations[len(networks)]["id"]  # first provider org
    for (key, name, product), net_id in zip(NETWORKS, network_ids, strict=True):
        directory.insurance_plans.append(
            plannet.build_insurance_plan(
                plan_key=key, name=f"{name} Plan", plan_type_code=product,
                plan_type_display=product, owned_by_org_id=owner_org_id,
                network_ids=[net_id],
            )
        )

    return directory

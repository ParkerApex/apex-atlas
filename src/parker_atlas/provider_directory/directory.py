"""
Da Vinci PDEX Plan-Net provider directory generation.

Builds a synthetic payer provider directory — Networks, provider Organizations,
Locations, Practitioners, PractitionerRoles, HealthcareServices, InsurancePlans,
and Endpoints — conforming to the Plan-Net profiles.

Coherence: the directory is built from the **same reference roster**
(`practitioners.csv` / `locations.csv`) that patient encounters draw from via
`core.provider.sample_care_team`. So a practitioner (or facility) referenced by
a patient's Encounter/Claim carries an NPI that also appears in this published
directory — the claims ↔ directory linkage the CMS Interoperability rule tests.

Serialization to a bulk NDJSON directory + manifest lives in
:mod:`parker_atlas.provider_directory.publish`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from parker_atlas.fhir import plannet
from parker_atlas.references import load_locations, load_practitioners
from parker_atlas.scheduling.links import CLINIC_SITES

SERVICE_CATEGORY_CODE = "17"
SERVICE_CATEGORY_DISPLAY = "General Practice"

# Two networks the directory advertises.
NETWORKS = (
    ("ppo", "Apex Choice PPO Network", "PPO"),
    ("hmo", "Apex Care HMO Network", "HMO"),
)

# City → (lat, long) lookup so roster Locations can carry a geographic position
# where the city is known.
_CITY_GEO = {s.city: (s.latitude, s.longitude) for s in CLINIC_SITES}


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


def generate_provider_directory() -> ProviderDirectory:
    """Generate a Plan-Net directory from the shared provider roster (deterministic)."""
    practitioner_rows = load_practitioners()
    location_rows = load_locations()
    directory = ProviderDirectory()

    networks = [plannet.build_network(network_key=k, name=n) for k, n, _ in NETWORKS]
    network_ids = [n["id"] for n in networks]
    directory.organizations.extend(networks)

    # Provider Organizations + Endpoints — one per unique facility NPI.
    facility_name: dict[str, str] = {}
    for loc in location_rows:
        facility_name.setdefault(loc.facility_npi, loc.facility_name)
    facility_org_id: dict[str, str] = {}
    for npi, name in facility_name.items():
        org = plannet.build_organization(npi=npi, name=name)
        directory.organizations.append(org)
        facility_org_id[npi] = org["id"]
        directory.endpoints.append(
            plannet.build_endpoint(
                org_npi=npi, org_id=org["id"],
                base_url=f"https://fhir.example.org/plannet/{npi}",
            )
        )

    # Locations (one per roster row), keyed by facility NPI for role linkage.
    location_ids_by_facility: dict[str, list[str]] = {}
    for loc in location_rows:
        lat, lon = _CITY_GEO.get(loc.city, (None, None))
        location = plannet.build_location(
            org_npi=loc.facility_npi, name=loc.location_name,
            line=loc.line, city=loc.city, state=loc.state, postal_code=loc.postal_code,
            latitude=lat, longitude=lon,
        )
        directory.locations.append(location)
        location_ids_by_facility.setdefault(loc.facility_npi, []).append(location["id"])

    # A practitioner staffing an encounter class is listed at a facility that
    # offers that class of care (hospital for IMP/EMER, office otherwise).
    def facility_for_class(class_code: str) -> tuple[str, str, str]:
        want = {"IMP": "hosp", "EMER": "hosp"}.get(class_code, "prov")
        for loc in location_rows:
            role = "hosp" if loc.facility_role == "hosp" else "prov"
            if role == want:
                return loc.facility_npi, facility_org_id[loc.facility_npi], loc.location_name
        loc = location_rows[0]
        return loc.facility_npi, facility_org_id[loc.facility_npi], loc.location_name

    seen_services: set[str] = set()
    for idx, prac_row in enumerate(practitioner_rows):
        practitioner = plannet.build_practitioner(
            npi=prac_row.npi, family=prac_row.family, given=prac_row.given,
            prefix=prac_row.prefix, taxonomy_code=prac_row.taxonomy_code,
            taxonomy_display=prac_row.taxonomy_display,
        )
        directory.practitioners.append(practitioner)

        fac_npi, org_id, loc_name = facility_for_class(prac_row.encounter_class)
        loc_id = plannet.location_id_for(fac_npi, loc_name)

        service = plannet.build_healthcare_service(
            org_npi=fac_npi, location_id=loc_id, service_key=prac_row.taxonomy_code,
            category_code=SERVICE_CATEGORY_CODE, category_display=SERVICE_CATEGORY_DISPLAY,
            type_code=prac_row.taxonomy_code, type_display=prac_row.taxonomy_display,
        )
        if service["id"] not in seen_services:
            seen_services.add(service["id"])
            directory.healthcare_services.append(service)

        network_id = network_ids[idx % len(network_ids)]
        directory.practitioner_roles.append(
            plannet.build_practitioner_role(
                practitioner_id=practitioner["id"], org_id=org_id, location_id=loc_id,
                service_id=service["id"], network_id=network_id,
                role_code=prac_row.taxonomy_code, role_display=prac_row.taxonomy_display,
                specialty_code=prac_row.taxonomy_code, specialty_display=prac_row.taxonomy_display,
                accepting_new_patients=(idx % 4 != 0),
            )
        )

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

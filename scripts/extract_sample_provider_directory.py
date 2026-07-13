"""Extract readable examples from the CMS Connectathon 2026 Da Vinci Plan-Net
(`$bulk-publish`) provider-directory dataset.

The published directory NDJSON spreads one provider's information across seven
files (Practitioner, PractitionerRole, Organization, Location, HealthcareService,
InsurancePlan, Endpoint). This script pulls one provider's complete slice and
writes:

- Per-resource-type sample arrays (``Practitioner.example.json``,
  ``PractitionerRole.example.json``, ``Organization.example.json``, …) — a few
  real resources per type so you can see each shape without opening the NDJSON.
- ``plan-net-provider.example.json`` — one self-contained FHIR **collection
  Bundle** for a single practitioner: Practitioner → PractitionerRole →
  (provider Organization, Network Organization, Location, HealthcareService) plus
  the InsurancePlan(s) and Endpoint(s) that complete the graph. Read one file to
  see the whole Plan-Net directory graph for a provider.

Output goes to ``samples/cms-connectathon-2026/provider-directory/examples/``.

Run:

    python scripts/extract_sample_provider_directory.py
"""

from __future__ import annotations

import json
from pathlib import Path

from fhir.resources.R4B.bundle import Bundle as _Bundle

REPO_ROOT = Path(__file__).resolve().parent.parent
PD_DIR = REPO_ROOT / "samples" / "cms-connectathon-2026" / "provider-directory"
OUT_DIR = PD_DIR / "examples"

# Example base for the collection Bundle so relative references resolve.
FHIR_BASE = "https://parkerapex.com/atlas/fhir"
# Anchor the walkthrough on this provider (the first, test-pinned roster entry).
ANCHOR_NPI = "1000000012"


def load_ndjson(path: Path):
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")


def _id(ref: str) -> str:
    return ref.split("/", 1)[1]


def main() -> None:
    practitioners = list(load_ndjson(PD_DIR / "Practitioner.ndjson"))
    roles = list(load_ndjson(PD_DIR / "PractitionerRole.ndjson"))
    orgs = list(load_ndjson(PD_DIR / "Organization.ndjson"))
    locations = list(load_ndjson(PD_DIR / "Location.ndjson"))
    services = list(load_ndjson(PD_DIR / "HealthcareService.ndjson"))
    plans = list(load_ndjson(PD_DIR / "InsurancePlan.ndjson"))
    endpoints = list(load_ndjson(PD_DIR / "Endpoint.ndjson"))

    by_id = lambda seq: {r["id"]: r for r in seq}
    orgs_by_id = by_id(orgs)
    locs_by_id = by_id(locations)
    svc_by_id = by_id(services)

    # Anchor practitioner + their role.
    practitioner = next(
        p for p in practitioners
        if any(i.get("value") == ANCHOR_NPI for i in p.get("identifier", []))
    )
    role = next(
        r for r in roles if _id(r["practitioner"]["reference"]) == practitioner["id"]
    )

    provider_org = orgs_by_id[_id(role["organization"]["reference"])]
    network_ids = [
        _id(e["valueReference"]["reference"])
        for e in role.get("extension", [])
        if e.get("url", "").endswith("network-reference")
    ]
    network_orgs = [orgs_by_id[nid] for nid in network_ids]
    location = locs_by_id[_id(role["location"][0]["reference"])]
    service = svc_by_id[_id(role["healthcareService"][0]["reference"])]

    # InsurancePlan(s) advertising any of this provider's networks.
    network_id_set = set(network_ids)
    example_plans = [
        p for p in plans
        if any(_id(n["reference"]) in network_id_set for n in p.get("network", []))
    ]
    # Endpoint(s) managed by the provider organization.
    example_endpoints = [
        e for e in endpoints
        if _id(e["managingOrganization"]["reference"]) == provider_org["id"]
    ]

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Per-type readable arrays. Organization shows the provider org + its
    # network(s); a couple of extra practitioners/roles give a feel for the file.
    extra_pracs = [p for p in practitioners if p["id"] != practitioner["id"]][:2]
    extra_roles = [
        r for r in roles
        if _id(r["practitioner"]["reference"]) in {p["id"] for p in extra_pracs}
    ]
    write_json(OUT_DIR / "Practitioner.example.json", [practitioner, *extra_pracs])
    write_json(OUT_DIR / "PractitionerRole.example.json", [role, *extra_roles])
    write_json(OUT_DIR / "Organization.example.json", [provider_org, *network_orgs])
    write_json(OUT_DIR / "Location.example.json", [location])
    write_json(OUT_DIR / "HealthcareService.example.json", [service])
    write_json(OUT_DIR / "InsurancePlan.example.json", example_plans)
    write_json(OUT_DIR / "Endpoint.example.json", example_endpoints)

    # Self-contained walkthrough Bundle (collection) for the anchor provider.
    graph = [
        practitioner, role, provider_org, *network_orgs, location, service,
        *example_plans, *example_endpoints,
    ]
    bundle = {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            {"fullUrl": f"{FHIR_BASE}/{r['resourceType']}/{r['id']}", "resource": r}
            for r in graph
        ],
    }
    _Bundle.model_validate(bundle)
    write_json(OUT_DIR / "plan-net-provider.example.json", bundle)

    _write_readme(practitioner, role, provider_org, network_orgs, location,
                  service, example_plans, example_endpoints)

    name = practitioner["name"][0]
    display = " ".join(name.get("prefix", []) + name.get("given", []) + [name["family"]])
    print(
        f"provider={display} ({ANCHOR_NPI}) org={provider_org['name']} "
        f"networks={len(network_orgs)} plans={len(example_plans)} "
        f"endpoints={len(example_endpoints)}"
    )


def _write_readme(prac, role, org, networks, location, service, plans, endpoints) -> None:
    name = prac["name"][0]
    display = " ".join(name.get("prefix", []) + name.get("given", []) + [name["family"]])
    specialty = role["specialty"][0]["coding"][0]["display"]
    net_names = ", ".join(n["name"] for n in networks)
    plan_names = ", ".join(p["name"] for p in plans)
    body = (
        "# Sample provider-directory records\n\n"
        "Readable, pretty-printed samples of the Da Vinci **Plan-Net** "
        "(`$bulk-publish`) provider directory in [`../`](../). The published "
        "directory spreads one provider's information across seven NDJSON files; "
        "these files let you see the shape of each resource, and how they link "
        "into a single provider's directory entry, without opening the NDJSON.\n\n"
        "All records below center on one example provider — "
        f"**{display}**, {specialty}, at **{org['name']}** "
        f"({location['address']['city']}, {location['address']['state']}), "
        f"in-network for: {net_names}.\n\n"
        "## Files\n\n"
        "| File | What it shows |\n| --- | --- |\n"
        "| `Practitioner.example.json` | The provider `Practitioner` (NPI, name, NUCC board qualification) — plus two others for context. |\n"
        "| `PractitionerRole.example.json` | The `PractitionerRole` tying practitioner ↔ organization ↔ location ↔ service ↔ network, with specialty and accepting-new-patients. |\n"
        "| `Organization.example.json` | The provider `Organization` (`type = prov`) and the payer `Network`(s) (`type = ntwk`) it belongs to. |\n"
        "| `Location.example.json` | The practice `Location` (address, geo `position`, managing organization). |\n"
        "| `HealthcareService.example.json` | The `HealthcareService` this org offers at that location. |\n"
        "| `InsurancePlan.example.json` | The `InsurancePlan`(s) whose network includes this provider. |\n"
        "| `Endpoint.example.json` | The FHIR `Endpoint`(s) for the provider organization. |\n"
        "| `plan-net-provider.example.json` | A single self-contained FHIR **collection Bundle** stitching the whole graph together: Practitioner → PractitionerRole → Organization / Network / Location / HealthcareService → InsurancePlan / Endpoint. |\n\n"
        "## Reference graph\n\n"
        "```\n"
        "Practitioner  <-practitioner-  PractitionerRole  -organization->  Organization (prov)\n"
        "                                     |  -location->  Location\n"
        "                                     |  -healthcareService->  HealthcareService  -providedBy->  Organization\n"
        "                                     +- (network-reference ext) ->  Organization (ntwk)  <-network-  InsurancePlan\n"
        "                                                                          Organization (prov)  <-managingOrganization-  Endpoint\n"
        "```\n\n"
        f"This provider's entry is in-network for **{net_names}** "
        f"and appears in these plan(s): {plan_names}.\n\n"
        "See the full readable roster in [`../PROVIDERS.md`](../PROVIDERS.md).\n\n"
        "Regenerate with `python scripts/extract_sample_provider_directory.py`.\n"
    )
    (OUT_DIR / "README.md").write_text(body, encoding="utf-8")


if __name__ == "__main__":
    main()

# Da Vinci Plan-Net provider directory (`$bulk-publish`)

Apex Atlas can publish a synthetic **payer provider directory** conforming to the
[Da Vinci PDEX Plan-Net](http://hl7.org/fhir/us/davinci-pdex-plan-net/)
implementation guide — the provider-directory surface referenced by the CMS
Interoperability & Patient Access rule.

The output is a bulk NDJSON directory plus a `$bulk-publish` manifest, one file
per resource type:

| File | Resource | Role |
| --- | --- | --- |
| `bulk-publish-manifest.json` | — | Links the NDJSON files via `output[]`. |
| `Organization.ndjson` | Organization | Provider organizations **and** Networks (`type = ntwk`). |
| `Location.ndjson` | Location | Practice sites with address + geo `position`, managed by an Organization. |
| `Practitioner.ndjson` | Practitioner | Providers with NPI identifiers and a board qualification (NUCC taxonomy). |
| `PractitionerRole.ndjson` | PractitionerRole | The core directory record: practitioner ↔ organization ↔ location ↔ healthcare service ↔ network, with specialty and accepting-new-patients. |
| `HealthcareService.ndjson` | HealthcareService | Services offered by an Organization at a Location. |
| `InsurancePlan.ndjson` | InsurancePlan | Plans referencing their network(s). |
| `Endpoint.ndjson` | Endpoint | A FHIR base URL per Organization. |

All resources carry the Plan-Net `meta.profile`, use relative references
(`Organization/<id>`, …), and validate against the `fhir.resources` R4B models.

## CLI

```bash
atlas publish-provider-directory [OPTIONS]
```

| Option | Default | Description |
| --- | --- | --- |
| `--out`, `-o` | `./provider-directory` | Output directory. |
| `--sites` | `15` | Number of provider Organizations/Locations (1–40). |
| `--practitioners-per-site` | `4` | Practitioners generated at each site. |
| `--base-url` | `https://example.org/provider-directory` | Base URL advertised in the manifest `output[]`. |

```bash
atlas publish-provider-directory --sites 15 --practitioners-per-site 4 --out ./provider-directory
```

## Python API

```python
from pathlib import Path
from parker_atlas.provider_directory import (
    DirectoryConfig, generate_provider_directory, write_bulk_publish,
)

directory = generate_provider_directory(DirectoryConfig(sites=15, practitioners_per_site=4))
write_bulk_publish(
    directory, Path("./provider-directory"),
    base_url="https://example.org/provider-directory",
    transaction_time="2026-07-12T00:00:00Z",
)
```

## Reference graph

```
PractitionerRole  -practitioner->  Practitioner
                  -organization->  Organization (type prov)
                  -location->      Location
                  -healthcareService->  HealthcareService  -providedBy->  Organization
                  -network-reference(ext)->  Organization (type ntwk)
InsurancePlan     -network->       Organization (type ntwk)
Location          -managingOrganization->  Organization
Endpoint          -managingOrganization->  Organization
```

## Conformance note

Resources carry the Plan-Net profiles and populate the primary must-support
elements (identifiers, active, type, specialty/NUCC taxonomy, network-reference
and accepting-new-patients extensions, geographic position). This is
**alignment** for connectathon and integration testing, not a formally
IG-validated conformance run. Data is fully synthetic (`HTEST` tag; example
NPIs and endpoints).

# Sample provider-directory records

Readable, pretty-printed samples of the Da Vinci **Plan-Net** (`$bulk-publish`) provider directory in [`../`](../). The published directory spreads one provider's information across seven NDJSON files; these files let you see the shape of each resource, and how they link into a single provider's directory entry, without opening the NDJSON.

All records below center on one example provider — **Dr. Anika Patel**, Internal Medicine, at **APEX Atlas Primary Care - Cambridge** (Cambridge, MA), in-network for: Apex Choice PPO Network.

## Files

| File | What it shows |
| --- | --- |
| `Practitioner.example.json` | The provider `Practitioner` (NPI, name, NUCC board qualification) — plus two others for context. |
| `PractitionerRole.example.json` | The `PractitionerRole` tying practitioner ↔ organization ↔ location ↔ service ↔ network, with specialty and accepting-new-patients. |
| `Organization.example.json` | The provider `Organization` (`type = prov`) and the payer `Network`(s) (`type = ntwk`) it belongs to. |
| `Location.example.json` | The practice `Location` (address, geo `position`, managing organization). |
| `HealthcareService.example.json` | The `HealthcareService` this org offers at that location. |
| `InsurancePlan.example.json` | The `InsurancePlan`(s) whose network includes this provider. |
| `Endpoint.example.json` | The FHIR `Endpoint`(s) for the provider organization. |
| `plan-net-provider.example.json` | A single self-contained FHIR **collection Bundle** stitching the whole graph together: Practitioner → PractitionerRole → Organization / Network / Location / HealthcareService → InsurancePlan / Endpoint. |

## Reference graph

```
Practitioner  <-practitioner-  PractitionerRole  -organization->  Organization (prov)
                                     |  -location->  Location
                                     |  -healthcareService->  HealthcareService  -providedBy->  Organization
                                     +- (network-reference ext) ->  Organization (ntwk)  <-network-  InsurancePlan
                                                                          Organization (prov)  <-managingOrganization-  Endpoint
```

This provider's entry is in-network for **Apex Choice PPO Network** and appears in these plan(s): Apex Choice PPO Network Plan.

See the full readable roster in [`../PROVIDERS.md`](../PROVIDERS.md).

Regenerate with `python scripts/extract_sample_provider_directory.py`.

# IG conformance report — PASS

Dataset: `samples/cms-connectathon-2026` — 168596 resources

## Resource types

| Type | Count |
| --- | ---: |
| Appointment | 2848 |
| Condition | 23396 |
| Coverage | 18232 |
| Encounter | 30978 |
| Endpoint | 12 |
| HealthcareService | 44 |
| Immunization | 6249 |
| InsurancePlan | 11 |
| Location | 55 |
| MedicationRequest | 6275 |
| Observation | 45651 |
| Organization | 28 |
| Patient | 20009 |
| Practitioner | 154 |
| PractitionerRole | 154 |
| Schedule | 84 |
| Slot | 14416 |

## Declared profiles (`meta.profile`)

| Profile | Resources |
| --- | ---: |
| `http://hl7.org/fhir/us/core/StructureDefinition/us-core-blood-pressure|6.1.0` | 27387 |
| `http://hl7.org/fhir/us/core/StructureDefinition/us-core-condition-problems-health-concerns|6.1.0` | 23396 |
| `http://hl7.org/fhir/us/core/StructureDefinition/us-core-coverage|6.1.0` | 18232 |
| `http://hl7.org/fhir/us/core/StructureDefinition/us-core-encounter|6.1.0` | 30978 |
| `http://hl7.org/fhir/us/core/StructureDefinition/us-core-immunization|6.1.0` | 6249 |
| `http://hl7.org/fhir/us/core/StructureDefinition/us-core-laboratory-result-observation|6.1.0` | 6041 |
| `http://hl7.org/fhir/us/core/StructureDefinition/us-core-medicationrequest|6.1.0` | 6275 |
| `http://hl7.org/fhir/us/core/StructureDefinition/us-core-organization|6.1.0` | 12 |
| `http://hl7.org/fhir/us/core/StructureDefinition/us-core-patient|6.1.0` | 20009 |
| `http://hl7.org/fhir/us/core/StructureDefinition/us-core-vital-signs|6.1.0` | 12223 |
| `http://hl7.org/fhir/us/davinci-pdex-plan-net/StructureDefinition/plannet-Endpoint` | 12 |
| `http://hl7.org/fhir/us/davinci-pdex-plan-net/StructureDefinition/plannet-HealthcareService` | 44 |
| `http://hl7.org/fhir/us/davinci-pdex-plan-net/StructureDefinition/plannet-InsurancePlan` | 4 |
| `http://hl7.org/fhir/us/davinci-pdex-plan-net/StructureDefinition/plannet-Location` | 13 |
| `http://hl7.org/fhir/us/davinci-pdex-plan-net/StructureDefinition/plannet-Network` | 4 |
| `http://hl7.org/fhir/us/davinci-pdex-plan-net/StructureDefinition/plannet-Organization` | 12 |
| `http://hl7.org/fhir/us/davinci-pdex-plan-net/StructureDefinition/plannet-Practitioner` | 154 |
| `http://hl7.org/fhir/us/davinci-pdex-plan-net/StructureDefinition/plannet-PractitionerRole` | 154 |

## Native checks

- Structural (fhir.resources R4B): **168596/168596 valid**
- Referential integrity: **246912/246912 references resolved**

## External HL7 validator

_Not run: no validator_cli.jar found (pass --validator-jar or set ATLAS_FHIR_VALIDATOR_JAR); native checks only_

> Full US Core / C4BB / Plan-Net profile conformance requires the official HL7 FHIR validator. Provide it with `--validator-jar PATH` (or `$ATLAS_FHIR_VALIDATOR_JAR`) to include an external pass.

# Scheduling publication: HL7 validator results

Run on 2026-11-01 with the official HL7 FHIR validator (`validator_cli.jar`,
hapifhir/org.hl7.fhir.core latest release), FHIR 4.0.1, live terminology at
https://tx.fhir.org, loading `hl7.fhir.us.core#6.1.0` and the SMART Scheduling
Links extension definitions in `src/parker_atlas/scheduling/ig/` (the spec
publishes those URLs without a FHIR package).

```
java -jar validator_cli.jar <dir> -version 4.0.1 \
  -ig hl7.fhir.us.core#6.1.0 -ig src/parker_atlas/scheduling/ig
```

| Resources validated | Count | Errors | Warnings |
| --- | ---: | ---: | ---: |
| Organization | 1 | 0 | 0 |
| Practitioner (US Core) | 40 | 0 | 0 |
| PractitionerRole (US Core) | 40 | 0 | 0 |
| Location | 40 | 0 | 0 |
| Schedule | 80 | 0 | 0 |
| Slot (all 280 of Sam Torres's + 160 sampled) | 440 | 0 | 0 |
| **Total** | **641** | **0** | **0** |

All 641 outcomes are information-level only. `atlas validate samples/cms-connectathon-2026 --refs`
resolves 253,500 / 253,500 references across 173,473 resources.

## NPIs

Practitioner and Organization NPIs come from
`src/parker_atlas/references/tables/scheduling_npis.csv`: Luhn-valid numbers
the public CMS NPPES NPI Registry API reported as unassigned on 2026-11-01.
The 39 generated clinician names also return no NPPES matches. Re-verify with
`python scripts/verify_npis_nppes.py --verify src/parker_atlas/references/tables/scheduling_npis.csv`.

Note: the name "Sam Torres" does match a real clinician in NPPES (different NPI).
The dataset's Sam Torres is synthetic, with an unassigned NPI.

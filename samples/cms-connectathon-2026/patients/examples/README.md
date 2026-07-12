# Sample patient records

Human-readable, pretty-printed FHIR R4 **transaction Bundles** for a few real patients drawn from the 20,000-patient bulk export in [`../`](../). Each file is a complete record for one patient — the `Patient` plus all of their linked resources (conditions, encounters, observations, medications, immunizations, coverage) — so you can read a whole patient in one file instead of scanning the large NDJSON.

These are identical to what `atlas generate --format fhir-r4` emits for these patients; the full population lives in the `*.ndjson` files one directory up.

| File | Entries | Conditions |
| --- | ---: | --- |
| `GPX-SYN-0000000549-6.json` | 28 | Chronic kidney disease due to hypertension (disorder), Diabetes mellitus (disorder), Diabetic chronic kidney disease (disorder), Essential hypertension (disorder), General examination of patient (procedure), Retinopathy due to diabetes mellitus (disorder) |
| `GPX-SYN-0000000279-0.json` | 25 | Diabetes mellitus (disorder), Diabetic chronic kidney disease (disorder), Essential hypertension (disorder), General examination of patient (procedure), Retinopathy due to diabetes mellitus (disorder) |
| `GPX-SYN-0000003057-7.json` | 20 | Diabetes mellitus (disorder), Essential hypertension (disorder), General examination of patient (procedure) |
| `GPX-SYN-0000000049-7.json` | 9 | Essential hypertension (disorder) |
| `GPX-SYN-0000000001-8.json` | 3 | (no active conditions) |

Regenerate with `python scripts/extract_sample_patients.py`.

# Provider roster

The synthetic clinician + facility roster that populates both the Plan-Net provider directory here and the `Practitioner` / `PractitionerRole` references on patient encounters (`atlas generate --with-providers`). NPIs are dummy values in the `1xxxxxxxxx` (individual) / `2xxxxxxxxx` (organization) blocks, each with a valid CMS NPPES Luhn check digit; taxonomy codes are from the NUCC Health Care Provider Taxonomy. Everything is synthetic.

**40 providers** across **34 specialties** at **10 facilities**.

## Providers

| NPI | Name | Specialty | Taxonomy (NUCC) | Setting | Facility |
| --- | --- | --- | --- | --- | --- |
| `1000000012` | Dr. Anika Patel | Internal Medicine | `207R00000X` | Ambulatory | APEX Atlas Primary Care - Cambridge |
| `1000000020` | Dr. Linh Nguyen | Family Medicine | `207Q00000X` | Ambulatory | APEX Atlas Primary Care - Somerville |
| `1000000038` | Dr. Mateo Garcia | Family Medicine | `207Q00000X` | Ambulatory | APEX Atlas Primary Care - Cambridge |
| `1000000046` | Dr. Chinwe Okafor | Cardiovascular Disease | `207RC0000X` | Ambulatory | APEX Atlas Cardiology Clinic |
| `1000000053` | Dr. Marcus Hughes | Cardiovascular Disease | `207RC0000X` | Ambulatory | APEX Atlas Cardiology Clinic |
| `1000000061` | Dr. Hannah Schmidt | Emergency Medicine | `207P00000X` | Emergency | APEX Atlas General Hospital |
| `1000000079` | Dr. Daniel Cohen | Emergency Medicine | `207P00000X` | Emergency | APEX Atlas General Hospital |
| `1000000087` | Dr. Jisoo Park | Hospitalist | `208M00000X` | Inpatient | APEX Atlas General Hospital |
| `1000000095` | Dr. Yusuf Ahmed | Endocrinology Diabetes & Metabolism | `207RE0101X` | Ambulatory | APEX Atlas Multispecialty Center - Boston |
| `1000000103` | Dr. Sofia Ivanov | Nephrology | `207RN0300X` | Ambulatory | APEX Atlas Multispecialty Center - Boston |
| `1000000111` | Dr. Elena Rossi | Pulmonary Disease | `207RP1001X` | Ambulatory | APEX Atlas Multispecialty Center - Boston |
| `1000000129` | Dr. Daniel Kim | Gastroenterology | `207RG0100X` | Ambulatory | APEX Atlas Multispecialty Center - Boston |
| `1000000137` | Dr. Petra Novak | Infectious Disease | `207RI0200X` | Ambulatory | APEX Atlas Multispecialty Center - Boston |
| `1000000145` | Dr. Lukas Bauer | Rheumatology | `207RR0500X` | Ambulatory | APEX Atlas Multispecialty Center - Boston |
| `1000000152` | Dr. Camila Silva | Pediatrics | `208000000X` | Ambulatory | APEX Atlas Women's & Children's Center |
| `1000000160` | Dr. Tunde Adeyemi | Pediatrics | `208000000X` | Ambulatory | APEX Atlas Women's & Children's Center |
| `1000000178` | Dr. Maria Johnson | Obstetrics & Gynecology | `207V00000X` | Ambulatory | APEX Atlas Women's & Children's Center |
| `1000000186` | Dr. Anton Meyer | Neurology | `2084N0400X` | Ambulatory | APEX Atlas Neuroscience & Behavioral Health |
| `1000000194` | Dr. Greta Fischer | Psychiatry | `2084P0800X` | Ambulatory | APEX Atlas Neuroscience & Behavioral Health |
| `1000000202` | Dr. Hiro Tanaka | Surgery | `208600000X` | Inpatient | APEX Atlas Surgical & Orthopedic Center |
| `1000000210` | Dr. Marco Bianchi | Orthopaedic Surgery | `207X00000X` | Inpatient | APEX Atlas Surgical & Orthopedic Center |
| `1000000228` | Dr. Ana Costa | Ophthalmology | `207W00000X` | Ambulatory | APEX Atlas Surgical & Orthopedic Center |
| `1000000236` | Dr. Erik Larsson | Diagnostic Radiology | `2085R0202X` | Ambulatory | APEX Atlas Imaging Center |
| `1000000244` | Sofia Reyes | Nurse Practitioner | `363L00000X` | Ambulatory | APEX Atlas Primary Care - Cambridge |
| `1000000251` | Jordan Brooks | Physician Assistant | `363A00000X` | Ambulatory | APEX Atlas Primary Care - Somerville |
| `1000000269` | Dr. Rafael Delgado | Interventional Cardiology | `207RI0011X` | Ambulatory | APEX Atlas Cardiology Clinic |
| `1000000277` | Dr. Grace Whitfield | Clinical Cardiac Electrophysiology | `207RC0001X` | Ambulatory | APEX Atlas Cardiology Clinic |
| `1000000285` | Dr. Kenji Yamamoto | Hematology & Oncology | `207RH0003X` | Ambulatory | APEX Atlas Cancer Center |
| `1000000293` | Dr. Ngozi Abara | Radiation Oncology | `2085R0001X` | Ambulatory | APEX Atlas Cancer Center |
| `1000000301` | Dr. Milena Petrova | Dermatology | `207N00000X` | Ambulatory | APEX Atlas Multispecialty Center - Boston |
| `1000000319` | Dr. Sean OConnor | Urology | `208800000X` | Ambulatory | APEX Atlas Surgical & Orthopedic Center |
| `1000000327` | Dr. Layla Haddad | Otolaryngology | `207Y00000X` | Ambulatory | APEX Atlas Surgical & Orthopedic Center |
| `1000000335` | Dr. Jonas Weber | Allergy & Immunology | `207K00000X` | Ambulatory | APEX Atlas Multispecialty Center - Boston |
| `1000000343` | Dr. Kwame Mensah | Physical Medicine & Rehabilitation | `208100000X` | Ambulatory | APEX Atlas Multispecialty Center - Boston |
| `1000000350` | Dr. Chiara Romano | Anesthesiology | `207L00000X` | Inpatient | APEX Atlas General Hospital |
| `1000000368` | Dr. Nils Andersson | Critical Care Medicine | `207RC0200X` | Inpatient | APEX Atlas General Hospital |
| `1000000376` | Dr. Naomi Blackwell | Maternal & Fetal Medicine | `207VM0101X` | Ambulatory | APEX Atlas Women's & Children's Center |
| `1000000384` | Dr. Ruth Feldman | Geriatric Medicine | `207RG0300X` | Ambulatory | APEX Atlas Primary Care - Cambridge |
| `1000000392` | Dr. Ama Osei | Internal Medicine | `207R00000X` | Ambulatory | APEX Atlas Primary Care - Cambridge |
| `1000000400` | Dr. Diego Vargas | Pediatrics | `208000000X` | Ambulatory | APEX Atlas Women's & Children's Center |

## Facilities

| Organization NPI | Facility | City |
| --- | --- | --- |
| `2000000010` | APEX Atlas General Hospital | Boston, MA |
| `2000000028` | APEX Atlas Cardiology Clinic | Boston, MA |
| `2000000036` | APEX Atlas Primary Care - Cambridge | Cambridge, MA |
| `2000000044` | APEX Atlas Primary Care - Somerville | Somerville, MA |
| `2000000051` | APEX Atlas Multispecialty Center - Boston | Boston, MA |
| `2000000069` | APEX Atlas Women's & Children's Center | Cambridge, MA |
| `2000000077` | APEX Atlas Neuroscience & Behavioral Health | Boston, MA |
| `2000000085` | APEX Atlas Surgical & Orthopedic Center | Boston, MA |
| `2000000093` | APEX Atlas Imaging Center | Cambridge, MA |
| `2000000101` | APEX Atlas Cancer Center | Boston, MA |

Regenerate with `python scripts/build_provider_roster_table.py`. The machine-readable directory (Plan-Net NDJSON + manifest) is in this same folder; see [`../../../docs/provider-directory.md`](../../../docs/provider-directory.md).

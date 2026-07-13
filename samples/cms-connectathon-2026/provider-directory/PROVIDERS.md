# Provider roster

The synthetic clinician + facility roster that populates both the Plan-Net provider directory here and the `Practitioner` / `PractitionerRole` references on patient encounters (`atlas generate --with-providers`). NPIs are dummy values in the `1xxxxxxxxx` (individual) / `2xxxxxxxxx` (organization) blocks, each with a valid CMS NPPES Luhn check digit; taxonomy codes are from the NUCC Health Care Provider Taxonomy. Everything is synthetic.

**150 providers** across **34 specialties** at **10 facilities**.

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
| `1000000418` | Dr. Elena Reddy | Internal Medicine | `207R00000X` | Ambulatory | APEX Atlas Primary Care - Cambridge |
| `1000000426` | Dr. Emil Johansen | Internal Medicine | `207R00000X` | Ambulatory | APEX Atlas Primary Care - Somerville |
| `1000000434` | Dr. Rania Adebayo | Internal Medicine | `207R00000X` | Ambulatory | APEX Atlas Multispecialty Center - Boston |
| `1000000442` | Dr. Sofia Ferreira | Internal Medicine | `207R00000X` | Ambulatory | APEX Atlas Primary Care - Cambridge |
| `1000000459` | Dr. Malik Ndiaye | Internal Medicine | `207R00000X` | Ambulatory | APEX Atlas Primary Care - Somerville |
| `1000000467` | Dr. Ivan Ustinov | Internal Medicine | `207R00000X` | Ambulatory | APEX Atlas Multispecialty Center - Boston |
| `1000000475` | Dr. Mateus Farrell | Internal Medicine | `207R00000X` | Ambulatory | APEX Atlas Primary Care - Cambridge |
| `1000000483` | Dr. Freya Cho | Internal Medicine | `207R00000X` | Ambulatory | APEX Atlas Primary Care - Somerville |
| `1000000491` | Dr. Malik Rahman | Internal Medicine | `207R00000X` | Ambulatory | APEX Atlas Multispecialty Center - Boston |
| `1000000509` | Dr. Anja Iversen | Internal Medicine | `207R00000X` | Ambulatory | APEX Atlas Primary Care - Cambridge |
| `1000000517` | Dr. Ethan Okonkwo | Internal Medicine | `207R00000X` | Ambulatory | APEX Atlas Primary Care - Somerville |
| `1000000525` | Dr. Tomas Quintero | Internal Medicine | `207R00000X` | Ambulatory | APEX Atlas Multispecialty Center - Boston |
| `1000000533` | Dr. Nikolai Toledo | Internal Medicine | `207R00000X` | Ambulatory | APEX Atlas Primary Care - Cambridge |
| `1000000541` | Dr. Imani Karlsson | Internal Medicine | `207R00000X` | Ambulatory | APEX Atlas Primary Care - Somerville |
| `1000000558` | Dr. Sean Walsh | Internal Medicine | `207R00000X` | Ambulatory | APEX Atlas Multispecialty Center - Boston |
| `1000000566` | Dr. Kofi Krishnan | Internal Medicine | `207R00000X` | Ambulatory | APEX Atlas Primary Care - Cambridge |
| `1000000574` | Dr. Emil Solberg | Internal Medicine | `207R00000X` | Ambulatory | APEX Atlas Primary Care - Somerville |
| `1000000582` | Dr. Yara Ferreira | Internal Medicine | `207R00000X` | Ambulatory | APEX Atlas Multispecialty Center - Boston |
| `1000000590` | Dr. Diego Cho | Family Medicine | `207Q00000X` | Ambulatory | APEX Atlas Primary Care - Cambridge |
| `1000000608` | Dr. Ingrid Karlsson | Family Medicine | `207Q00000X` | Ambulatory | APEX Atlas Primary Care - Somerville |
| `1000000616` | Dr. Luka Karlsson | Family Medicine | `207Q00000X` | Ambulatory | APEX Atlas Primary Care - Cambridge |
| `1000000624` | Dr. Farah Quintero | Family Medicine | `207Q00000X` | Ambulatory | APEX Atlas Primary Care - Somerville |
| `1000000632` | Dr. Divya Ibrahim | Family Medicine | `207Q00000X` | Ambulatory | APEX Atlas Primary Care - Cambridge |
| `1000000640` | Dr. Farah Mahmoud | Family Medicine | `207Q00000X` | Ambulatory | APEX Atlas Primary Care - Somerville |
| `1000000657` | Dr. Ethan Rahman | Family Medicine | `207Q00000X` | Ambulatory | APEX Atlas Primary Care - Cambridge |
| `1000000665` | Dr. Malik Tremblay | Family Medicine | `207Q00000X` | Ambulatory | APEX Atlas Primary Care - Somerville |
| `1000000673` | Dr. Luka Kovac | Family Medicine | `207Q00000X` | Ambulatory | APEX Atlas Primary Care - Cambridge |
| `1000000681` | Dr. Oscar Dumont | Family Medicine | `207Q00000X` | Ambulatory | APEX Atlas Primary Care - Somerville |
| `1000000699` | Dr. Freya Ismail | Family Medicine | `207Q00000X` | Ambulatory | APEX Atlas Primary Care - Cambridge |
| `1000000707` | Dr. Sean Mahmoud | Family Medicine | `207Q00000X` | Ambulatory | APEX Atlas Primary Care - Somerville |
| `1000000715` | Dr. Meera Rahman | Family Medicine | `207Q00000X` | Ambulatory | APEX Atlas Primary Care - Cambridge |
| `1000000723` | Dr. Yara Ueda | Family Medicine | `207Q00000X` | Ambulatory | APEX Atlas Primary Care - Somerville |
| `1000000731` | Lucia Zheng | Nurse Practitioner | `363L00000X` | Ambulatory | APEX Atlas Primary Care - Cambridge |
| `1000000749` | Lucia Lindqvist | Nurse Practitioner | `363L00000X` | Ambulatory | APEX Atlas Primary Care - Somerville |
| `1000000756` | Bjorn Solberg | Nurse Practitioner | `363L00000X` | Ambulatory | APEX Atlas Women's & Children's Center |
| `1000000764` | Elsa Dumont | Nurse Practitioner | `363L00000X` | Ambulatory | APEX Atlas Multispecialty Center - Boston |
| `1000000772` | Yuki Johansen | Nurse Practitioner | `363L00000X` | Ambulatory | APEX Atlas Primary Care - Cambridge |
| `1000000780` | Ingrid Solberg | Nurse Practitioner | `363L00000X` | Ambulatory | APEX Atlas Primary Care - Somerville |
| `1000000798` | Yara Voss | Nurse Practitioner | `363L00000X` | Ambulatory | APEX Atlas Women's & Children's Center |
| `1000000806` | Wei Ndiaye | Nurse Practitioner | `363L00000X` | Ambulatory | APEX Atlas Multispecialty Center - Boston |
| `1000000814` | Hugo Egorov | Nurse Practitioner | `363L00000X` | Ambulatory | APEX Atlas Primary Care - Cambridge |
| `1000000822` | Yuki Vasquez | Nurse Practitioner | `363L00000X` | Ambulatory | APEX Atlas Primary Care - Somerville |
| `1000000830` | Chiara Haas | Nurse Practitioner | `363L00000X` | Ambulatory | APEX Atlas Women's & Children's Center |
| `1000000848` | Yara Hoffman | Nurse Practitioner | `363L00000X` | Ambulatory | APEX Atlas Multispecialty Center - Boston |
| `1000000855` | Dr. Hana Ibrahim | Pediatrics | `208000000X` | Ambulatory | APEX Atlas Women's & Children's Center |
| `1000000863` | Dr. Elsa Cho | Pediatrics | `208000000X` | Ambulatory | APEX Atlas Women's & Children's Center |
| `1000000871` | Dr. Ling Ustinov | Pediatrics | `208000000X` | Ambulatory | APEX Atlas Women's & Children's Center |
| `1000000889` | Dr. Rania Tremblay | Pediatrics | `208000000X` | Ambulatory | APEX Atlas Women's & Children's Center |
| `1000000897` | Dr. Kai Beckett | Pediatrics | `208000000X` | Ambulatory | APEX Atlas Women's & Children's Center |
| `1000000905` | Dr. Ivan Abbott | Pediatrics | `208000000X` | Ambulatory | APEX Atlas Women's & Children's Center |
| `1000000913` | Dr. Mira Laurent | Pediatrics | `208000000X` | Ambulatory | APEX Atlas Women's & Children's Center |
| `1000000921` | Bjorn Krishnan | Physician Assistant | `363A00000X` | Ambulatory | APEX Atlas Primary Care - Cambridge |
| `1000000939` | Leila Gupta | Physician Assistant | `363A00000X` | Ambulatory | APEX Atlas Primary Care - Somerville |
| `1000000947` | Elena Farrell | Physician Assistant | `363A00000X` | Ambulatory | APEX Atlas Surgical & Orthopedic Center |
| `1000000954` | Hugo Jansen | Physician Assistant | `363A00000X` | Ambulatory | APEX Atlas Primary Care - Cambridge |
| `1000000962` | Ana Ueda | Physician Assistant | `363A00000X` | Ambulatory | APEX Atlas Primary Care - Somerville |
| `1000000970` | Beatriz Halvorsen | Physician Assistant | `363A00000X` | Ambulatory | APEX Atlas Surgical & Orthopedic Center |
| `1000000988` | Mira Saito | Physician Assistant | `363A00000X` | Ambulatory | APEX Atlas Primary Care - Cambridge |
| `1000000996` | Dr. Hugo Baptiste | Emergency Medicine | `207P00000X` | Emergency | APEX Atlas General Hospital |
| `1000001002` | Dr. Viktor Laurent | Emergency Medicine | `207P00000X` | Emergency | APEX Atlas General Hospital |
| `1000001010` | Dr. Amara Diaz | Emergency Medicine | `207P00000X` | Emergency | APEX Atlas General Hospital |
| `1000001028` | Dr. Nikolai Ueda | Emergency Medicine | `207P00000X` | Emergency | APEX Atlas General Hospital |
| `1000001036` | Dr. Viktor Adebayo | Emergency Medicine | `207P00000X` | Emergency | APEX Atlas General Hospital |
| `1000001044` | Dr. Emil Contreras | Hospitalist | `208M00000X` | Inpatient | APEX Atlas General Hospital |
| `1000001051` | Dr. Ingrid Diaz | Hospitalist | `208M00000X` | Inpatient | APEX Atlas General Hospital |
| `1000001069` | Dr. Emil Saito | Hospitalist | `208M00000X` | Inpatient | APEX Atlas General Hospital |
| `1000001077` | Dr. Elena Cho | Hospitalist | `208M00000X` | Inpatient | APEX Atlas General Hospital |
| `1000001085` | Dr. Kofi Reddy | Hospitalist | `208M00000X` | Inpatient | APEX Atlas General Hospital |
| `1000001093` | Dr. Hugo Dumont | Obstetrics & Gynecology | `207V00000X` | Ambulatory | APEX Atlas Women's & Children's Center |
| `1000001101` | Dr. Ethan Moreau | Obstetrics & Gynecology | `207V00000X` | Ambulatory | APEX Atlas Women's & Children's Center |
| `1000001119` | Dr. Hana Karlsson | Obstetrics & Gynecology | `207V00000X` | Ambulatory | APEX Atlas Women's & Children's Center |
| `1000001127` | Dr. Elsa Moreau | Obstetrics & Gynecology | `207V00000X` | Ambulatory | APEX Atlas Women's & Children's Center |
| `1000001135` | Dr. Mateus Quintero | Psychiatry | `2084P0800X` | Ambulatory | APEX Atlas Neuroscience & Behavioral Health |
| `1000001143` | Dr. Aaron Cho | Psychiatry | `2084P0800X` | Ambulatory | APEX Atlas Neuroscience & Behavioral Health |
| `1000001150` | Dr. Sofia Egorov | Psychiatry | `2084P0800X` | Ambulatory | APEX Atlas Neuroscience & Behavioral Health |
| `1000001168` | Dr. Yara Iversen | Psychiatry | `2084P0800X` | Ambulatory | APEX Atlas Neuroscience & Behavioral Health |
| `1000001176` | Dr. Pedro Toledo | Cardiovascular Disease | `207RC0000X` | Ambulatory | APEX Atlas Cardiology Clinic |
| `1000001184` | Dr. Hana Toledo | Cardiovascular Disease | `207RC0000X` | Ambulatory | APEX Atlas Cardiology Clinic |
| `1000001192` | Dr. Soren Haas | Cardiovascular Disease | `207RC0000X` | Ambulatory | APEX Atlas Cardiology Clinic |
| `1000001200` | Dr. Aisha Haas | Diagnostic Radiology | `2085R0202X` | Ambulatory | APEX Atlas Imaging Center |
| `1000001218` | Dr. Bjorn Haas | Diagnostic Radiology | `2085R0202X` | Ambulatory | APEX Atlas Imaging Center |
| `1000001226` | Dr. Nikolai Xu | Diagnostic Radiology | `2085R0202X` | Ambulatory | APEX Atlas Imaging Center |
| `1000001234` | Dr. Sofia Dumont | Anesthesiology | `207L00000X` | Inpatient | APEX Atlas General Hospital |
| `1000001242` | Dr. Elena Moreau | Anesthesiology | `207L00000X` | Inpatient | APEX Atlas General Hospital |
| `1000001259` | Dr. Sean Ferreira | Anesthesiology | `207L00000X` | Inpatient | APEX Atlas General Hospital |
| `1000001267` | Dr. Oscar Lozano | Neurology | `2084N0400X` | Ambulatory | APEX Atlas Neuroscience & Behavioral Health |
| `1000001275` | Dr. Luka Dumont | Neurology | `2084N0400X` | Ambulatory | APEX Atlas Neuroscience & Behavioral Health |
| `1000001283` | Dr. Yuki Moreau | Dermatology | `207N00000X` | Ambulatory | APEX Atlas Multispecialty Center - Boston |
| `1000001291` | Dr. Anja Falk | Dermatology | `207N00000X` | Ambulatory | APEX Atlas Multispecialty Center - Boston |
| `1000001309` | Dr. Elsa Yildiz | Orthopaedic Surgery | `207X00000X` | Inpatient | APEX Atlas Surgical & Orthopedic Center |
| `1000001317` | Dr. Pedro Cho | Orthopaedic Surgery | `207X00000X` | Inpatient | APEX Atlas Surgical & Orthopedic Center |
| `1000001325` | Dr. Amara Kovac | Gastroenterology | `207RG0100X` | Ambulatory | APEX Atlas Multispecialty Center - Boston |
| `1000001333` | Dr. Elena Johansen | Gastroenterology | `207RG0100X` | Ambulatory | APEX Atlas Multispecialty Center - Boston |
| `1000001341` | Dr. Noah Vasquez | Surgery | `208600000X` | Inpatient | APEX Atlas Surgical & Orthopedic Center |
| `1000001358` | Dr. Marcus Baptiste | Surgery | `208600000X` | Inpatient | APEX Atlas Surgical & Orthopedic Center |
| `1000001366` | Dr. Ana Ndiaye | Ophthalmology | `207W00000X` | Ambulatory | APEX Atlas Surgical & Orthopedic Center |
| `1000001374` | Dr. Yuki Rahman | Ophthalmology | `207W00000X` | Ambulatory | APEX Atlas Surgical & Orthopedic Center |
| `1000001382` | Dr. Nia Tremblay | Hematology & Oncology | `207RH0003X` | Ambulatory | APEX Atlas Cancer Center |
| `1000001390` | Dr. Viktor Kovac | Endocrinology Diabetes & Metabolism | `207RE0101X` | Ambulatory | APEX Atlas Multispecialty Center - Boston |
| `1000001408` | Dr. Sofia Tremblay | Nephrology | `207RN0300X` | Ambulatory | APEX Atlas Multispecialty Center - Boston |
| `1000001416` | Dr. Freya Egorov | Pulmonary Disease | `207RP1001X` | Ambulatory | APEX Atlas Multispecialty Center - Boston |
| `1000001424` | Dr. Andre Baptiste | Infectious Disease | `207RI0200X` | Ambulatory | APEX Atlas Multispecialty Center - Boston |
| `1000001432` | Dr. Farah Adebayo | Rheumatology | `207RR0500X` | Ambulatory | APEX Atlas Multispecialty Center - Boston |
| `1000001440` | Dr. Yuki Ustinov | Urology | `208800000X` | Ambulatory | APEX Atlas Surgical & Orthopedic Center |
| `1000001457` | Dr. Rania Quintero | Otolaryngology | `207Y00000X` | Ambulatory | APEX Atlas Surgical & Orthopedic Center |
| `1000001465` | Dr. Kai Yildiz | Physical Medicine & Rehabilitation | `208100000X` | Ambulatory | APEX Atlas Multispecialty Center - Boston |
| `1000001473` | Dr. Tomas Reddy | Critical Care Medicine | `207RC0200X` | Inpatient | APEX Atlas General Hospital |
| `1000001481` | Dr. Zara Krishnan | Geriatric Medicine | `207RG0300X` | Ambulatory | APEX Atlas Primary Care - Cambridge |
| `1000001499` | Dr. Ana Gallardo | Radiation Oncology | `2085R0001X` | Ambulatory | APEX Atlas Cancer Center |
| `1000001507` | Dr. Ling Xu | Interventional Cardiology | `207RI0011X` | Ambulatory | APEX Atlas Cardiology Clinic |

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

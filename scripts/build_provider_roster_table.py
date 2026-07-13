"""Render a human-readable provider roster (Markdown) from the reference CSVs.

Reads `practitioners.csv` / `locations.csv` (the roster that populates both
patient-encounter care teams and the Da Vinci Plan-Net directory) and writes a
readable table of providers, specialties, and NPIs plus the facility list to
``samples/cms-connectathon-2026/provider-directory/PROVIDERS.md``.

Run:

    python scripts/build_provider_roster_table.py
"""

from __future__ import annotations

from pathlib import Path

from parker_atlas.references import load_locations, load_practitioners

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT = REPO_ROOT / "samples" / "cms-connectathon-2026" / "provider-directory" / "PROVIDERS.md"

CLASS_LABEL = {"AMB": "Ambulatory", "EMER": "Emergency", "IMP": "Inpatient"}


def main() -> None:
    practitioners = load_practitioners()
    locations = load_locations()

    facility_name = {}
    facility_city = {}
    for loc in locations:
        facility_name.setdefault(loc.facility_npi, loc.facility_name)
        facility_city.setdefault(loc.facility_npi, f"{loc.city}, {loc.state}")

    lines: list[str] = []
    lines.append("# Provider roster")
    lines.append("")
    lines.append(
        "The synthetic clinician + facility roster that populates both the "
        "Plan-Net provider directory here and the `Practitioner` / "
        "`PractitionerRole` references on patient encounters "
        "(`atlas generate --with-providers`). NPIs are dummy values in the "
        "`1xxxxxxxxx` (individual) / `2xxxxxxxxx` (organization) blocks, each "
        "with a valid CMS NPPES Luhn check digit; taxonomy codes are from the "
        "NUCC Health Care Provider Taxonomy. Everything is synthetic."
    )
    lines.append("")
    lines.append(
        f"**{len(practitioners)} providers** across "
        f"**{len({p.taxonomy_display for p in practitioners})} specialties** at "
        f"**{len(facility_name)} facilities**."
    )
    lines.append("")
    lines.append("## Providers")
    lines.append("")
    lines.append("| NPI | Name | Specialty | Taxonomy (NUCC) | Setting | Facility |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for p in practitioners:
        prefix = f"{p.prefix} " if p.prefix else ""
        lines.append(
            f"| `{p.npi}` | {prefix}{p.given} {p.family} | {p.taxonomy_display} | "
            f"`{p.taxonomy_code}` | {CLASS_LABEL.get(p.encounter_class, p.encounter_class)} | "
            f"{facility_name.get(p.facility_npi, p.facility_npi)} |"
        )
    lines.append("")
    lines.append("## Facilities")
    lines.append("")
    lines.append("| Organization NPI | Facility | City |")
    lines.append("| --- | --- | --- |")
    for npi in sorted(facility_name):
        lines.append(f"| `{npi}` | {facility_name[npi]} | {facility_city[npi]} |")
    lines.append("")
    lines.append(
        "Regenerate with `python scripts/build_provider_roster_table.py`. The "
        "machine-readable directory (Plan-Net NDJSON + manifest) is in this same "
        "folder; see [`../../../docs/provider-directory.md`](../../../docs/provider-directory.md)."
    )
    lines.append("")

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT} — {len(practitioners)} providers, {len(facility_name)} facilities")


if __name__ == "__main__":
    main()

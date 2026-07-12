"""
CARIN Blue Button (C4BB) alignment for payer resources.

Opt-in enrichment that stamps CARIN Consumer Directed Payer Data Exchange
(C4BB) profiles and the required top-level elements onto the Patient, Coverage,
payer Organization, and ExplanationOfBenefit resources Atlas already produces,
so the payer slice aligns with the CMS Interoperability & Patient Access rule.

Scope / honesty: this adds the C4BB `meta.profile` canonicals plus the
required/must-support **top-level** elements Atlas can populate correctly
(Coverage member identifier + class, EOB billablePeriod + payee + coded
adjudication categories, Organization.active). It is *alignment*, not a full
IG-validated conformance — deeper C4BB slicing (careTeam, supportingInfo billing
network/type-of-bill, diagnosis sequencing) is out of scope. See
docs/known-limitations.md.
"""

from __future__ import annotations

from typing import Any

C4BB_VERSION = "2.1.0"
_BASE = "http://hl7.org/fhir/us/carin-bb/StructureDefinition"
C4BB_PATIENT = f"{_BASE}/C4BB-Patient|{C4BB_VERSION}"
C4BB_COVERAGE = f"{_BASE}/C4BB-Coverage|{C4BB_VERSION}"
C4BB_ORGANIZATION = f"{_BASE}/C4BB-Organization|{C4BB_VERSION}"
C4BB_EOB_PROFESSIONAL = (
    f"{_BASE}/C4BB-ExplanationOfBenefit-Professional-NonClinician|{C4BB_VERSION}"
)

V2_0203 = "http://terminology.hl7.org/CodeSystem/v2-0203"
ADJUDICATION_SYSTEM = "http://terminology.hl7.org/CodeSystem/adjudication"
PAYEE_TYPE_SYSTEM = "http://terminology.hl7.org/CodeSystem/payeetype"
PARKER_SUBSCRIBER_ID_SYSTEM = "https://parkerapex.com/atlas/subscriber"


def _add_profile(resource: dict[str, Any], profile: str) -> None:
    meta = resource.setdefault("meta", {})
    profiles = meta.setdefault("profile", [])
    if profile not in profiles:
        profiles.append(profile)


def _enrich_patient(patient: dict[str, Any]) -> None:
    _add_profile(patient, C4BB_PATIENT)


def _enrich_organization(org: dict[str, Any]) -> None:
    _add_profile(org, C4BB_ORGANIZATION)
    org.setdefault("active", True)  # C4BB-Organization.active is required


def _enrich_coverage(coverage: dict[str, Any]) -> None:
    _add_profile(coverage, C4BB_COVERAGE)

    # C4BB requires a member-number identifier (type MB). Derive it from the
    # Coverage.subscriberId already present.
    sub_id = coverage.get("subscriberId")
    if sub_id:
        identifiers = coverage.setdefault("identifier", [])
        has_mb = any(
            c.get("code") == "MB"
            for ident in identifiers
            for c in ident.get("type", {}).get("coding", [])
        )
        if not has_mb:
            identifiers.append(
                {
                    "type": {
                        "coding": [
                            {"system": V2_0203, "code": "MB", "display": "Member Number"}
                        ]
                    },
                    "system": PARKER_SUBSCRIBER_ID_SYSTEM,
                    "value": sub_id,
                }
            )

    # C4BB-Coverage must-supports both a 'group' and a 'plan' class. The base
    # builder emits 'plan' when an InsurancePlan is present; add a matching
    # 'group' so both are available.
    classes = coverage.get("class")
    if classes:
        codes = {
            c.get("code")
            for cls in classes
            for c in cls.get("type", {}).get("coding", [])
        }
        if "plan" in codes and "group" not in codes:
            plan = next(
                cls for cls in classes
                if any(
                    c.get("code") == "plan"
                    for c in cls.get("type", {}).get("coding", [])
                )
            )
            classes.append(
                {
                    "type": {
                        "coding": [
                            {
                                "system": "http://terminology.hl7.org/CodeSystem/coverage-class",
                                "code": "group",
                                "display": "Group",
                            }
                        ]
                    },
                    "value": plan.get("value", ""),
                    "name": plan.get("name", ""),
                }
            )


def _enrich_eob(eob: dict[str, Any]) -> None:
    _add_profile(eob, C4BB_EOB_PROFESSIONAL)

    # C4BB requires billablePeriod; derive the service date from `created`.
    if "billablePeriod" not in eob and eob.get("created"):
        day = str(eob["created"])[:10]
        eob["billablePeriod"] = {"start": day, "end": day}

    # C4BB requires payee; the provider is the payee for a professional claim.
    if "payee" not in eob and eob.get("provider"):
        eob["payee"] = {
            "type": {
                "coding": [
                    {"system": PAYEE_TYPE_SYSTEM, "code": "provider", "display": "Provider"}
                ]
            },
            "party": eob["provider"],
        }

    # Coded adjudication categories: attach the HL7 adjudication CodeSystem to
    # the bare category codes the base builder emits.
    for item in eob.get("item", []):
        for adj in item.get("adjudication", []):
            for coding in adj.get("category", {}).get("coding", []):
                coding.setdefault("system", ADJUDICATION_SYSTEM)
    for total in eob.get("total", []):
        for coding in total.get("category", {}).get("coding", []):
            coding.setdefault("system", ADJUDICATION_SYSTEM)


_ENRICHERS = {
    "Patient": _enrich_patient,
    "Organization": _enrich_organization,
    "Coverage": _enrich_coverage,
    "ExplanationOfBenefit": _enrich_eob,
}


def enrich_carin_bb(resources: list[dict[str, Any]]) -> None:
    """Apply C4BB profiles + required elements to a patient's resources, in place.

    Resources of types Atlas doesn't map to CARIN BB (Condition, Observation,
    Claim, …) are left untouched.
    """
    for resource in resources:
        enricher = _ENRICHERS.get(resource.get("resourceType", ""))
        if enricher is not None:
            enricher(resource)

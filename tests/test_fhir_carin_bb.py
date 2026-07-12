"""Tests for CARIN Blue Button (C4BB) enrichment."""

from __future__ import annotations

from parker_atlas.fhir.carin_bb import (
    C4BB_COVERAGE,
    C4BB_EOB_PROFESSIONAL,
    C4BB_ORGANIZATION,
    C4BB_PATIENT,
    enrich_carin_bb,
)


def _coverage() -> dict:
    return {
        "resourceType": "Coverage",
        "id": "cov-1",
        "meta": {"profile": ["http://hl7.org/fhir/us/core/StructureDefinition/us-core-coverage|6.1.0"]},
        "subscriberId": "SYN-ABC123",
        "class": [
            {"type": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/coverage-class", "code": "plan"}]}, "value": "P1", "name": "P1"}
        ],
    }


def _eob() -> dict:
    return {
        "resourceType": "ExplanationOfBenefit",
        "id": "eob-1",
        "created": "2026-04-25",
        "provider": {"reference": "Organization/o1"},
        "item": [{"adjudication": [{"category": {"coding": [{"code": "submitted"}]}}]}],
        "total": [{"category": {"coding": [{"code": "benefit"}]}}],
    }


class TestEnrichCoverage:
    def test_adds_profile_member_id_and_group_class(self):
        cov = _coverage()
        enrich_carin_bb([cov])
        assert C4BB_COVERAGE in cov["meta"]["profile"]
        types = [c["code"] for i in cov["identifier"] for c in i.get("type", {}).get("coding", [])]
        assert "MB" in types
        class_codes = {c["code"] for cls in cov["class"] for c in cls["type"]["coding"]}
        assert {"plan", "group"} <= class_codes


class TestEnrichEob:
    def test_adds_profile_billable_period_payee_and_adjudication_systems(self):
        eob = _eob()
        enrich_carin_bb([eob])
        assert C4BB_EOB_PROFESSIONAL in eob["meta"]["profile"]
        assert eob["billablePeriod"] == {"start": "2026-04-25", "end": "2026-04-25"}
        assert eob["payee"]["party"] == {"reference": "Organization/o1"}
        sys = eob["item"][0]["adjudication"][0]["category"]["coding"][0]["system"]
        assert sys == "http://terminology.hl7.org/CodeSystem/adjudication"
        assert eob["total"][0]["category"]["coding"][0]["system"]


class TestEnrichPatientAndOrg:
    def test_patient_and_org_profiles(self):
        patient = {"resourceType": "Patient", "id": "p1"}
        org = {"resourceType": "Organization", "id": "o1"}
        enrich_carin_bb([patient, org])
        assert C4BB_PATIENT in patient["meta"]["profile"]
        assert C4BB_ORGANIZATION in org["meta"]["profile"]
        assert org["active"] is True


class TestUntouched:
    def test_unmapped_types_untouched(self):
        cond = {"resourceType": "Condition", "id": "c1"}
        enrich_carin_bb([cond])
        assert "meta" not in cond

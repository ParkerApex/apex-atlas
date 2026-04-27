"""Tests for the Procedure FHIR builder."""

from __future__ import annotations

from datetime import date

from fhir.resources.R4B.procedure import Procedure

from parker_atlas.fhir.bundle import fullurl_for_gpx
from parker_atlas.fhir.procedure import (
    PARKER_PROCEDURE_IDENTIFIER_SYSTEM,
    US_CORE_PROCEDURE_PROFILE,
    build_procedure_resource,
    procedure_id,
)
from parker_atlas.gpx import Allocator, Category
from parker_atlas.modules.runtime import Coding


def _gpx():
    return Allocator(Category.SYNTHETIC).allocate()


_ECHO_CODE = Coding(
    system="http://snomed.info/sct",
    code="40701008",
    display="Echocardiography (procedure)",
)


class TestProcedureBuilder:
    def test_round_trips_through_fhir_resources(self):
        gpx = _gpx()
        resource = build_procedure_resource(
            gpx=gpx,
            patient_fullurl=fullurl_for_gpx(gpx),
            procedure_spec_id="hf_echo",
            code=_ECHO_CODE,
            performed_date=date(2026, 4, 1),
        )
        Procedure.model_validate(resource)

    def test_subject_references_patient_url(self):
        gpx = _gpx()
        purl = fullurl_for_gpx(gpx)
        resource = build_procedure_resource(
            gpx=gpx,
            patient_fullurl=purl,
            procedure_spec_id="hf_echo",
            code=_ECHO_CODE,
            performed_date=date(2026, 4, 1),
        )
        assert resource["subject"]["reference"] == purl

    def test_status_defaults_to_completed(self):
        gpx = _gpx()
        resource = build_procedure_resource(
            gpx=gpx,
            patient_fullurl=fullurl_for_gpx(gpx),
            procedure_spec_id="hf_echo",
            code=_ECHO_CODE,
            performed_date=date(2026, 4, 1),
        )
        assert resource["status"] == "completed"

    def test_carries_us_core_profile_and_synthetic_tag(self):
        gpx = _gpx()
        resource = build_procedure_resource(
            gpx=gpx,
            patient_fullurl=fullurl_for_gpx(gpx),
            procedure_spec_id="hf_echo",
            code=_ECHO_CODE,
            performed_date=date(2026, 4, 1),
        )
        assert US_CORE_PROCEDURE_PROFILE in resource["meta"]["profile"]
        tags = resource["meta"]["tag"]
        assert any(t.get("code") == "HTEST" for t in tags)

    def test_includes_required_identifier(self):
        gpx = _gpx()
        resource = build_procedure_resource(
            gpx=gpx,
            patient_fullurl=fullurl_for_gpx(gpx),
            procedure_spec_id="hf_echo",
            code=_ECHO_CODE,
            performed_date=date(2026, 4, 1),
        )
        identifiers = resource["identifier"]
        assert identifiers
        assert identifiers[0]["system"] == PARKER_PROCEDURE_IDENTIFIER_SYSTEM

    def test_id_is_deterministic_per_spec(self):
        gpx = Allocator(Category.SYNTHETIC).allocate()
        a = procedure_id(gpx, "hf_echo")
        b = procedure_id(gpx, "hf_echo")
        assert a == b
        assert a != procedure_id(gpx, "ihd_cath")

    def test_reason_code_when_provided(self):
        gpx = _gpx()
        reason = Coding(
            system="http://snomed.info/sct",
            code="84114007",
            display="Heart failure",
        )
        resource = build_procedure_resource(
            gpx=gpx,
            patient_fullurl=fullurl_for_gpx(gpx),
            procedure_spec_id="hf_echo",
            code=_ECHO_CODE,
            performed_date=date(2026, 4, 1),
            reason_code=reason,
        )
        assert resource["reasonCode"][0]["coding"][0]["code"] == "84114007"

    def test_encounter_link_when_provided(self):
        gpx = _gpx()
        resource = build_procedure_resource(
            gpx=gpx,
            patient_fullurl=fullurl_for_gpx(gpx),
            procedure_spec_id="hf_echo",
            code=_ECHO_CODE,
            performed_date=date(2026, 4, 1),
            encounter_fullurl="urn:uuid:abc",
        )
        assert resource["encounter"]["reference"] == "urn:uuid:abc"

    def test_no_encounter_means_no_encounter_field(self):
        gpx = _gpx()
        resource = build_procedure_resource(
            gpx=gpx,
            patient_fullurl=fullurl_for_gpx(gpx),
            procedure_spec_id="hf_echo",
            code=_ECHO_CODE,
            performed_date=date(2026, 4, 1),
        )
        assert "encounter" not in resource

"""Tests for the DocumentReference FHIR builder."""

from __future__ import annotations

import base64
from datetime import date

from fhir.resources.R4B.documentreference import DocumentReference

from parker_atlas.fhir.bundle import fullurl_for_gpx
from parker_atlas.fhir.document_reference import (
    LOINC_PROGRESS_NOTE,
    LOINC_SYSTEM,
    build_document_reference_resource,
    document_reference_id,
)
from parker_atlas.gpx import Allocator, Category


def _gpx():
    return Allocator(Category.SYNTHETIC).allocate()


class TestDocumentReferenceBuilder:
    def test_round_trips_through_fhir_resources(self):
        gpx = _gpx()
        purl = fullurl_for_gpx(gpx)
        resource = build_document_reference_resource(
            gpx=gpx,
            patient_fullurl=purl,
            doc_spec_id="progress_htn",
            note_text="# Note\n\nHello world.",
            authored_on=date(2026, 4, 23),
        )
        DocumentReference.model_validate(resource)

    def test_subject_references_patient_url(self):
        gpx = _gpx()
        purl = fullurl_for_gpx(gpx)
        resource = build_document_reference_resource(
            gpx=gpx,
            patient_fullurl=purl,
            doc_spec_id="progress_htn",
            note_text="body",
            authored_on=date(2026, 4, 23),
        )
        assert resource["subject"]["reference"] == purl

    def test_inline_content_is_base64_encoded(self):
        gpx = _gpx()
        body = "Patient is well today."
        resource = build_document_reference_resource(
            gpx=gpx,
            patient_fullurl=fullurl_for_gpx(gpx),
            doc_spec_id="progress_htn",
            note_text=body,
            authored_on=date(2026, 4, 23),
        )
        attachment = resource["content"][0]["attachment"]
        decoded = base64.b64decode(attachment["data"]).decode("utf-8")
        assert decoded == body
        assert attachment["contentType"] == "text/markdown"

    def test_loinc_type_defaults_to_progress_note(self):
        gpx = _gpx()
        resource = build_document_reference_resource(
            gpx=gpx,
            patient_fullurl=fullurl_for_gpx(gpx),
            doc_spec_id="progress_htn",
            note_text="x",
            authored_on=date(2026, 4, 23),
        )
        coding = resource["type"]["coding"][0]
        assert coding["system"] == LOINC_SYSTEM
        assert coding["code"] == LOINC_PROGRESS_NOTE

    def test_encounter_link_when_provided(self):
        gpx = _gpx()
        resource = build_document_reference_resource(
            gpx=gpx,
            patient_fullurl=fullurl_for_gpx(gpx),
            doc_spec_id="progress_htn",
            note_text="x",
            authored_on=date(2026, 4, 23),
            encounter_fullurl="urn:uuid:abc",
        )
        assert resource["context"]["encounter"][0]["reference"] == "urn:uuid:abc"

    def test_no_encounter_means_no_context_block(self):
        gpx = _gpx()
        resource = build_document_reference_resource(
            gpx=gpx,
            patient_fullurl=fullurl_for_gpx(gpx),
            doc_spec_id="progress_htn",
            note_text="x",
            authored_on=date(2026, 4, 23),
        )
        assert "context" not in resource

    def test_id_is_deterministic(self):
        gpx = Allocator(Category.SYNTHETIC).allocate()
        a = document_reference_id(gpx, "progress_htn")
        b = document_reference_id(gpx, "progress_htn")
        assert a == b
        assert a != document_reference_id(gpx, "progress_dm2")

    def test_carries_synthetic_meta_tag(self):
        gpx = _gpx()
        resource = build_document_reference_resource(
            gpx=gpx,
            patient_fullurl=fullurl_for_gpx(gpx),
            doc_spec_id="progress_htn",
            note_text="x",
            authored_on=date(2026, 4, 23),
        )
        tags = resource["meta"]["tag"]
        assert any(t.get("code") == "HTEST" for t in tags)

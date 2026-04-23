"""Tests for the fidelity expectation loader."""

from __future__ import annotations

import textwrap

import pytest

from parker_atlas.validation.expectations import (
    ExpectationError,
    list_bundled_expectations,
    load_bundled_expectation,
    load_expectation_from_str,
)


class TestLoader:
    def test_parses_minimal_expectation(self):
        yaml_text = textwrap.dedent(
            """
            module: t1
            version: 0.0.1
            source:
              name: placeholder
            metrics:
              - id: m
                kind: conditional_prevalence
                condition_code: "1234"
                condition_system: http://snomed.info/sct
                stratify_by: age_bracket
                tolerance: {kind: absolute, value: 0.05}
                targets:
                  "0-99": 0.5
            """
        )
        exp = load_expectation_from_str(yaml_text)
        assert exp.module == "t1"
        assert len(exp.metrics) == 1
        m = exp.metrics[0]
        assert m.targets[(0, 99)] == 0.5
        assert m.tolerance.value == 0.05

    def test_rejects_missing_top_level_key(self):
        with pytest.raises(ExpectationError, match="required"):
            load_expectation_from_str("module: x\nversion: 1\n")

    def test_rejects_non_mapping(self):
        with pytest.raises(ExpectationError, match="mapping"):
            load_expectation_from_str("- just\n- a\n- list")

    def test_rejects_unsupported_metric_kind(self):
        yaml_text = textwrap.dedent(
            """
            module: t
            version: 0.0.1
            metrics:
              - id: m
                kind: some_new_kind
                condition_code: x
                stratify_by: age_bracket
                tolerance: {kind: absolute, value: 0.05}
                targets:
                  "0-99": 0.5
            """
        )
        with pytest.raises(ExpectationError, match="unsupported metric kind"):
            load_expectation_from_str(yaml_text)

    def test_rejects_unsupported_stratification(self):
        yaml_text = textwrap.dedent(
            """
            module: t
            version: 0.0.1
            metrics:
              - id: m
                kind: conditional_prevalence
                condition_code: x
                stratify_by: zodiac_sign
                tolerance: {kind: absolute, value: 0.05}
                targets:
                  "0-99": 0.5
            """
        )
        with pytest.raises(ExpectationError, match="unsupported stratification"):
            load_expectation_from_str(yaml_text)

    def test_rejects_unsupported_tolerance_kind(self):
        yaml_text = textwrap.dedent(
            """
            module: t
            version: 0.0.1
            metrics:
              - id: m
                kind: conditional_prevalence
                condition_code: x
                stratify_by: age_bracket
                tolerance: {kind: relative, value: 0.1}
                targets:
                  "0-99": 0.5
            """
        )
        with pytest.raises(ExpectationError, match="tolerance kind"):
            load_expectation_from_str(yaml_text)

    def test_rejects_malformed_bracket(self):
        yaml_text = textwrap.dedent(
            """
            module: t
            version: 0.0.1
            metrics:
              - id: m
                kind: conditional_prevalence
                condition_code: x
                stratify_by: age_bracket
                tolerance: {kind: absolute, value: 0.05}
                targets:
                  "not-a-range": 0.5
            """
        )
        with pytest.raises(ExpectationError, match="bracket"):
            load_expectation_from_str(yaml_text)

    def test_bundled_hypertension_loads(self):
        exp = load_bundled_expectation("hypertension")
        assert exp.module == "hypertension"
        assert exp.metrics
        m = exp.metrics[0]
        assert m.condition_code == "59621000"
        assert (35, 54) in m.targets

    def test_list_bundled_expectations_includes_hypertension(self):
        assert "hypertension" in list_bundled_expectations()

    def test_unknown_bundled_expectation_raises(self):
        with pytest.raises(ExpectationError, match="no bundled expectation"):
            load_bundled_expectation("not-a-real-module")


class TestProvenance:
    def test_defaults_to_placeholder(self):
        yaml_text = textwrap.dedent(
            """
            module: t
            version: 0.0.1
            metrics:
              - id: m
                kind: conditional_prevalence
                condition_code: x
                stratify_by: age_bracket
                tolerance: {kind: absolute, value: 0.05}
                targets: {"0-99": 0.5}
            """
        )
        exp = load_expectation_from_str(yaml_text)
        assert exp.source.provenance == "placeholder"
        assert exp.source.citations == ()

    def test_parses_sourced_with_citations(self):
        yaml_text = textwrap.dedent(
            """
            module: t
            version: 0.0.1
            source:
              name: CDC NCHS
              provenance: sourced
              citations:
                - source: CDC NCHS FastStats
                  url: https://example.invalid
                  version: "2020"
                  accessed: "2026-04-23"
                  note: top-line reference
            metrics:
              - id: m
                kind: conditional_prevalence
                condition_code: x
                stratify_by: age_bracket
                tolerance: {kind: absolute, value: 0.05}
                targets: {"0-99": 0.5}
            """
        )
        exp = load_expectation_from_str(yaml_text)
        assert exp.source.provenance == "sourced"
        assert len(exp.source.citations) == 1
        c = exp.source.citations[0]
        assert c.source == "CDC NCHS FastStats"
        assert c.accessed == "2026-04-23"

    def test_rejects_unknown_provenance_level(self):
        yaml_text = textwrap.dedent(
            """
            module: t
            version: 0.0.1
            source: {provenance: bogus}
            metrics:
              - id: m
                kind: conditional_prevalence
                condition_code: x
                stratify_by: age_bracket
                tolerance: {kind: absolute, value: 0.05}
                targets: {"0-99": 0.5}
            """
        )
        with pytest.raises(ExpectationError, match="provenance"):
            load_expectation_from_str(yaml_text)

    def test_bundled_hypertension_is_placeholder(self):
        exp = load_bundled_expectation("hypertension")
        assert exp.source.provenance == "placeholder"
        assert exp.source.citations  # expectation declares its citations
        assert any("cdc" in c.url.lower() for c in exp.source.citations)

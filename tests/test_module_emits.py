"""Tests for module emit parsing, sampling, and CLI integration."""

from __future__ import annotations

import json
import random
import textwrap

import pytest
from typer.testing import CliRunner

from parker_atlas.cli import app
from parker_atlas.modules import (
    AllergyIntoleranceEmit,
    DiagnosticReportEmit,
    EncounterEmit,
    ImmunizationEmit,
    MedicationRequestEmit,
    ModuleError,
    ObservationEmit,
    SampledEncounter,
    SampledImmunization,
    SampledMedicationRequest,
    SampledObservation,
    load_module,
    load_module_from_str,
    run_module,
)

runner = CliRunner()


def _minimal_module_with_emits(emits_yaml: str) -> str:
    return textwrap.dedent(
        f"""
        module: t
        version: 0.0.1
        conditions:
          - id: c
            code:
              system: http://snomed.info/sct
              code: "1"
              display: Foo
            prevalence:
              "0-99": 1.0
            emits:
{textwrap.indent(textwrap.dedent(emits_yaml), '              ')}
        """
    )


class TestEmitParsing:
    def test_parses_encounter_emit(self):
        mod = load_module_from_str(
            _minimal_module_with_emits(
                """
                - resource_type: Encounter
                  spec_id: visit
                  encounter_class: AMB
                  type:
                    system: http://snomed.info/sct
                    code: "185349003"
                    display: Check up
                """
            )
        )
        emits = mod.conditions[0].emits
        assert len(emits) == 1
        assert isinstance(emits[0], EncounterEmit)
        assert emits[0].encounter_class == "AMB"

    def test_parses_single_value_observation_emit(self):
        mod = load_module_from_str(
            _minimal_module_with_emits(
                """
                - resource_type: Observation
                  spec_id: a1c
                  category: laboratory
                  code:
                    system: http://loinc.org
                    code: "4548-4"
                    display: A1C
                  value_range:
                    low: 6.5
                    high: 9.5
                    precision: 1
                  unit: "%"
                """
            )
        )
        emits = mod.conditions[0].emits
        assert len(emits) == 1
        assert isinstance(emits[0], ObservationEmit)
        assert emits[0].value_range.low == 6.5
        assert emits[0].unit == "%"

    def test_parses_multi_component_observation_emit(self):
        mod = load_module_from_str(
            _minimal_module_with_emits(
                """
                - resource_type: Observation
                  spec_id: bp
                  category: vital-signs
                  code:
                    system: http://loinc.org
                    code: "85354-9"
                    display: BP panel
                  components:
                    - code:
                        system: http://loinc.org
                        code: "8480-6"
                        display: Systolic
                      value_range: {low: 140, high: 180, precision: 0}
                      unit: mm[Hg]
                    - code:
                        system: http://loinc.org
                        code: "8462-4"
                        display: Diastolic
                      value_range: {low: 90, high: 110, precision: 0}
                      unit: mm[Hg]
                """
            )
        )
        emits = mod.conditions[0].emits
        assert isinstance(emits[0], ObservationEmit)
        assert len(emits[0].components) == 2

    def test_parses_medication_request_emit(self):
        mod = load_module_from_str(
            _minimal_module_with_emits(
                """
                - resource_type: MedicationRequest
                  spec_id: drug
                  probability: 0.5
                  medication:
                    system: http://www.nlm.nih.gov/research/umls/rxnorm
                    code: "197361"
                    display: Lisinopril 10 MG
                """
            )
        )
        emits = mod.conditions[0].emits
        assert isinstance(emits[0], MedicationRequestEmit)
        assert emits[0].probability == 0.5

    def test_parses_allergy_immunization_and_diagnostic_report_emits(self):
        mod = load_module_from_str(
            _minimal_module_with_emits(
                """
                - resource_type: Encounter
                  spec_id: visit
                  encounter_class: AMB
                  type: {system: s, code: "1", display: Visit}
                - resource_type: Observation
                  spec_id: total_cholesterol
                  link_to: visit
                  category: laboratory
                  code: {system: http://loinc.org, code: "2093-3", display: Total cholesterol}
                  value_range: {low: 120, high: 240, precision: 0}
                  unit: mg/dL
                - resource_type: DiagnosticReport
                  spec_id: lipid_report
                  link_to: visit
                  code: {system: http://loinc.org, code: "24331-1", display: Lipid panel}
                  results: [total_cholesterol]
                  conclusion: Synthetic lipid panel.
                - resource_type: AllergyIntolerance
                  spec_id: penicillin_allergy
                  code: {system: http://www.nlm.nih.gov/research/umls/rxnorm, code: "7980", display: Penicillin}
                  reaction: {system: http://snomed.info/sct, code: "247472004", display: Hives}
                - resource_type: Immunization
                  spec_id: flu_shot
                  link_to: visit
                  vaccine: {system: http://hl7.org/fhir/sid/cvx, code: "140", display: Influenza}
                """
            )
        )
        emits = mod.conditions[0].emits
        assert any(isinstance(e, DiagnosticReportEmit) for e in emits)
        assert any(isinstance(e, AllergyIntoleranceEmit) for e in emits)
        assert any(isinstance(e, ImmunizationEmit) for e in emits)

        dx = run_module(mod, age_years=40, sex="female", rng=random.Random(0))[0]
        assert any(isinstance(r, SampledImmunization) for r in dx.sampled_resources)

    def test_rejects_unknown_resource_type(self):
        with pytest.raises(ModuleError, match="unsupported resource_type"):
            load_module_from_str(
                _minimal_module_with_emits(
                    """
                    - resource_type: MagicSpell
                      spec_id: x
                    """
                )
            )

    def test_rejects_observation_with_value_and_components(self):
        with pytest.raises(ModuleError, match="exactly one of"):
            load_module_from_str(
                _minimal_module_with_emits(
                    """
                    - resource_type: Observation
                      spec_id: x
                      category: laboratory
                      code: {system: s, code: c, display: d}
                      unit: mg/dL
                      value_range: {low: 0, high: 100}
                      components:
                        - code: {system: s, code: c2, display: d2}
                          value_range: {low: 0, high: 100}
                          unit: mg/dL
                    """
                )
            )

    def test_rejects_observation_without_value_or_components(self):
        with pytest.raises(ModuleError, match="exactly one of"):
            load_module_from_str(
                _minimal_module_with_emits(
                    """
                    - resource_type: Observation
                      spec_id: x
                      category: laboratory
                      code: {system: s, code: c, display: d}
                    """
                )
            )

    def test_accepts_multiple_encounters_per_condition(self):
        # Multi-encounter is now supported (e.g., diagnosis visit at
        # onset + follow-up visit today).
        mod = load_module_from_str(
            _minimal_module_with_emits(
                """
                - resource_type: Encounter
                  spec_id: v1
                  encounter_class: AMB
                  type: {system: s, code: "1", display: d}
                - resource_type: Encounter
                  spec_id: v2
                  encounter_class: IMP
                  type: {system: s, code: "2", display: d}
                """
            )
        )
        assert sum(1 for e in mod.conditions[0].emits if isinstance(e, EncounterEmit)) == 2

    def test_rejects_duplicate_emit_spec_ids(self):
        with pytest.raises(ModuleError, match="duplicate emit spec_ids"):
            load_module_from_str(
                _minimal_module_with_emits(
                    """
                    - resource_type: Encounter
                      spec_id: visit
                      encounter_class: AMB
                      type: {system: s, code: "1", display: d}
                    - resource_type: Encounter
                      spec_id: visit
                      encounter_class: IMP
                      type: {system: s, code: "2", display: d}
                    """
                )
            )

    def test_rejects_link_to_unknown_encounter(self):
        with pytest.raises(ModuleError, match="link_to=.*does not match"):
            load_module_from_str(
                _minimal_module_with_emits(
                    """
                    - resource_type: Encounter
                      spec_id: visit
                      encounter_class: AMB
                      type: {system: s, code: "1", display: d}
                    - resource_type: Observation
                      spec_id: bp
                      link_to: nonexistent
                      category: vital-signs
                      code: {system: s, code: c, display: d}
                      value_range: {low: 1, high: 2}
                      unit: x
                    """
                )
            )

    def test_rejects_probability_outside_0_1(self):
        with pytest.raises(ModuleError, match="probability"):
            load_module_from_str(
                _minimal_module_with_emits(
                    """
                    - resource_type: MedicationRequest
                      spec_id: x
                      probability: 1.5
                      medication: {system: s, code: c, display: d}
                    """
                )
            )


class TestEmitSampling:
    def test_observation_value_falls_in_range(self):
        mod = load_module_from_str(
            _minimal_module_with_emits(
                """
                - resource_type: Observation
                  spec_id: a1c
                  category: laboratory
                  code: {system: http://loinc.org, code: "4548-4", display: A1C}
                  value_range: {low: 6.5, high: 9.5, precision: 1}
                  unit: "%"
                """
            )
        )
        rng = random.Random(0)
        diagnoses = run_module(mod, age_years=40, sex="female", rng=rng)
        assert len(diagnoses) == 1
        sr = diagnoses[0].sampled_resources[0]
        assert isinstance(sr, SampledObservation)
        assert 6.5 <= sr.value <= 9.5
        # precision=1 → one decimal place
        assert round(sr.value, 1) == sr.value

    def test_multi_component_observation_samples_each_component(self):
        mod = load_module("hypertension")
        # Try a handful of seeds until the condition fires. With male
        # 40-59 prevalence ≈ 0.559, well over half of seeds succeed on
        # the first try.
        diagnoses = []
        for seed in range(20):
            rng = random.Random(seed)
            diagnoses = run_module(mod, age_years=50, sex="male", rng=rng)
            if diagnoses:
                break
        assert diagnoses, "expected at least one seed in 0..19 to produce hypertension"
        obs = next(
            sr
            for sr in diagnoses[0].sampled_resources
            if isinstance(sr, SampledObservation) and sr.components
        )
        assert len(obs.components) == 2
        sys_val, dia_val = obs.components[0].value, obs.components[1].value
        assert 140 <= sys_val <= 180
        assert 90 <= dia_val <= 110

    def test_medication_probability_is_respected(self):
        """Over many runs, med emission frequency ≈ declared probability."""
        mod = load_module_from_str(
            _minimal_module_with_emits(
                """
                - resource_type: MedicationRequest
                  spec_id: drug
                  probability: 0.3
                  medication: {system: s, code: "c", display: d}
                """
            )
        )
        rng = random.Random(0)
        emits = 0
        total = 2000
        for _ in range(total):
            dx = run_module(mod, age_years=40, sex="female", rng=rng)
            if any(isinstance(r, SampledMedicationRequest) for r in dx[0].sampled_resources):
                emits += 1
        # 95% CI half-width at p=0.3, N=2000 ≈ 0.020
        assert abs(emits / total - 0.3) < 0.04

    def test_probability_one_always_emits(self):
        mod = load_module_from_str(
            _minimal_module_with_emits(
                """
                - resource_type: Encounter
                  spec_id: visit
                  encounter_class: AMB
                  type: {system: s, code: "1", display: d}
                """
            )
        )
        rng = random.Random(0)
        for _ in range(20):
            dx = run_module(mod, age_years=40, sex="female", rng=rng)
            assert any(isinstance(r, SampledEncounter) for r in dx[0].sampled_resources)


class TestCLIEndToEnd:
    def test_hypertensive_bundle_contains_all_linked_resources(self, tmp_path):
        result = runner.invoke(
            app,
            [
                "generate",
                "--patients", "20",
                "--seed", "42",
                "--module", "hypertension",
                "--out", str(tmp_path),
            ],
        )
        assert result.exit_code == 0, result.output

        # Find at least one hypertensive bundle with all four non-Patient resources.
        bundles_with_full_set = 0
        for f in sorted(tmp_path.glob("*.json")):
            data = json.loads(f.read_text())
            types = [e["resource"]["resourceType"] for e in data["entry"]]
            if {"Condition", "Encounter", "Observation"}.issubset(types):
                bundles_with_full_set += 1
                # Verify the Observation links to the Encounter.
                enc_entry = next(
                    e for e in data["entry"] if e["resource"]["resourceType"] == "Encounter"
                )
                obs_entry = next(
                    e for e in data["entry"] if e["resource"]["resourceType"] == "Observation"
                )
                assert obs_entry["resource"]["encounter"]["reference"] == enc_entry["fullUrl"]
        assert bundles_with_full_set >= 1, "expected some hypertensive bundles with Encounter + Observation"

    def test_cohort_harness_still_passes_on_updated_module(self, tmp_path):
        """The NHANES fidelity harness shouldn't regress under v0.3.0 emits."""
        result = runner.invoke(
            app,
            [
                "generate",
                "--patients", "20000",
                "--seed", "42",
                "--module", "hypertension",
                "--out", str(tmp_path),
            ],
        )
        assert result.exit_code == 0, result.output

        val = runner.invoke(
            app,
            [
                "validate",
                str(tmp_path),
                "--cohort",
                "--module", "hypertension",
                "--min-samples", "100",
                "--as-of", "2026-04-24",
            ],
        )
        assert val.exit_code == 0, val.output

    def test_structural_validator_accepts_multi_resource_bundles(self, tmp_path):
        gen = runner.invoke(
            app,
            [
                "generate",
                "--patients", "10",
                "--seed", "1",
                "--module", "hypertension",
                "--out", str(tmp_path),
            ],
        )
        assert gen.exit_code == 0, gen.output

        val = runner.invoke(app, ["validate", str(tmp_path)])
        assert val.exit_code == 0, val.output
        assert "0 failed" in val.output

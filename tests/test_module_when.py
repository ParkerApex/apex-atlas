"""Tests for `when: today | onset` field on emits."""

from __future__ import annotations

import json
import random
import textwrap
from datetime import date

import pytest
from typer.testing import CliRunner

from parker_atlas.cli import app
from parker_atlas.modules import (
    ALLOWED_EMIT_WHEN,
    ModuleError,
    SampledEncounter,
    SampledObservation,
    load_module_from_str,
    run_module,
)

runner = CliRunner()


def _module_with(emits_yaml: str, onset_yaml: str = "onset_age:\n  min: 25\n  max: 65") -> str:
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
{textwrap.indent(textwrap.dedent(onset_yaml), '            ')}
            emits:
{textwrap.indent(textwrap.dedent(emits_yaml), '              ')}
        """
    )


class TestWhenParsing:
    def test_default_when_is_today(self):
        mod = load_module_from_str(
            _module_with(
                """
                - resource_type: Encounter
                  spec_id: visit
                  encounter_class: AMB
                  type: {system: s, code: "1", display: d}
                """
            )
        )
        assert mod.conditions[0].emits[0].when == "today"

    def test_explicit_when_onset(self):
        mod = load_module_from_str(
            _module_with(
                """
                - resource_type: Encounter
                  spec_id: visit
                  when: onset
                  encounter_class: AMB
                  type: {system: s, code: "1", display: d}
                """
            )
        )
        assert mod.conditions[0].emits[0].when == "onset"

    def test_when_accepted_on_observation_and_medication(self):
        mod = load_module_from_str(
            _module_with(
                """
                - resource_type: Observation
                  spec_id: a1c
                  when: onset
                  category: laboratory
                  code: {system: s, code: c, display: d}
                  value_range: {low: 6.5, high: 9.5}
                  unit: "%"
                - resource_type: MedicationRequest
                  spec_id: drug
                  when: today
                  medication: {system: s, code: c, display: d}
                """
            )
        )
        emits = mod.conditions[0].emits
        assert emits[0].when == "onset"
        assert emits[1].when == "today"

    def test_rejects_unknown_when_value(self):
        with pytest.raises(ModuleError, match="when="):
            load_module_from_str(
                _module_with(
                    """
                    - resource_type: Encounter
                      spec_id: visit
                      when: never
                      encounter_class: AMB
                      type: {system: s, code: "1", display: d}
                    """
                )
            )

    def test_allowed_set_documents_choices(self):
        assert ALLOWED_EMIT_WHEN == ("today", "onset")


class TestWhenSampling:
    def test_when_today_uses_today(self):
        mod = load_module_from_str(
            _module_with(
                """
                - resource_type: Encounter
                  spec_id: v
                  when: today
                  encounter_class: AMB
                  type: {system: s, code: "1", display: d}
                """
            )
        )
        rng = random.Random(0)
        today = date(2026, 4, 25)
        diagnoses = run_module(mod, age_years=50, sex="female", rng=rng, today=today)
        sr = diagnoses[0].sampled_resources[0]
        assert isinstance(sr, SampledEncounter)
        assert sr.effective_date == today

    def test_when_onset_uses_onset_date(self):
        mod = load_module_from_str(
            _module_with(
                """
                - resource_type: Encounter
                  spec_id: v
                  when: onset
                  encounter_class: AMB
                  type: {system: s, code: "1", display: d}
                """
            )
        )
        rng = random.Random(0)
        today = date(2026, 4, 25)
        diagnoses = run_module(mod, age_years=50, sex="female", rng=rng, today=today)
        dx = diagnoses[0]
        sr = dx.sampled_resources[0]
        assert isinstance(sr, SampledEncounter)
        assert dx.onset_date is not None
        assert sr.effective_date == dx.onset_date
        # Should be in the past (or today) since age 50 fits the 25-65 onset window.
        assert sr.effective_date <= today

    def test_when_onset_falls_back_to_today_without_onset_age(self):
        # No onset_age declared on the module, so onset_date is None and
        # `when: onset` resolves to today.
        mod_yaml = textwrap.dedent(
            """
            module: t
            version: 0.0.1
            conditions:
              - id: c
                code: {system: s, code: "1", display: d}
                prevalence: {"0-99": 1.0}
                emits:
                  - resource_type: Encounter
                    spec_id: v
                    when: onset
                    encounter_class: AMB
                    type: {system: s, code: "1", display: d}
            """
        )
        mod = load_module_from_str(mod_yaml)
        rng = random.Random(0)
        today = date(2026, 4, 25)
        diagnoses = run_module(mod, age_years=50, sex="female", rng=rng, today=today)
        sr = diagnoses[0].sampled_resources[0]
        assert sr.effective_date == today

    def test_mixed_when_each_resource_uses_its_own(self):
        mod = load_module_from_str(
            _module_with(
                """
                - resource_type: Encounter
                  spec_id: visit
                  when: onset
                  encounter_class: AMB
                  type: {system: s, code: "1", display: d}
                - resource_type: Observation
                  spec_id: bp
                  when: today
                  category: vital-signs
                  code: {system: http://loinc.org, code: "85354-9", display: BP}
                  components:
                    - code: {system: http://loinc.org, code: "8480-6", display: SBP}
                      value_range: {low: 130, high: 160, precision: 0}
                      unit: mm[Hg]
                    - code: {system: http://loinc.org, code: "8462-4", display: DBP}
                      value_range: {low: 80, high: 100, precision: 0}
                      unit: mm[Hg]
                """
            )
        )
        rng = random.Random(0)
        today = date(2026, 4, 25)
        diagnoses = run_module(mod, age_years=70, sex="female", rng=rng, today=today)
        encs = [
            sr for sr in diagnoses[0].sampled_resources if isinstance(sr, SampledEncounter)
        ]
        obs = [
            sr for sr in diagnoses[0].sampled_resources if isinstance(sr, SampledObservation)
        ]
        assert encs[0].effective_date != today  # was sampled in the past
        assert obs[0].effective_date == today


class TestWhenEndToEnd:
    def test_hypertension_diagnosis_day_pattern(self, tmp_path):
        # Hypertension v0.5.0 uses when: onset on all three emits, so the
        # Condition / Encounter / Observation / MedicationRequest should
        # all share the same date.
        result = runner.invoke(
            app,
            [
                "generate",
                "--patients", "30",
                "--seed", "42",
                "--module", "hypertension",
                "--out", str(tmp_path),
            ],
        )
        assert result.exit_code == 0, result.output

        examined = 0
        for f in sorted(tmp_path.glob("*.json")):
            data = json.loads(f.read_text())
            cond = next(
                (e["resource"] for e in data["entry"] if e["resource"]["resourceType"] == "Condition"),
                None,
            )
            enc = next(
                (e["resource"] for e in data["entry"] if e["resource"]["resourceType"] == "Encounter"),
                None,
            )
            obs = next(
                (e["resource"] for e in data["entry"] if e["resource"]["resourceType"] == "Observation"),
                None,
            )
            if not (cond and enc and obs):
                continue
            onset = cond["onsetDateTime"]
            enc_start = enc["period"]["start"]
            obs_eff = obs["effectiveDateTime"][:10]  # strip Z if present
            assert onset == enc_start, (
                f"{f.name}: condition onset {onset} != encounter start {enc_start}"
            )
            assert obs_eff == onset, (
                f"{f.name}: observation effective {obs_eff} != condition onset {onset}"
            )
            examined += 1
        assert examined >= 1, "expected at least one fully-emitted hypertensive bundle"

    def test_observation_links_to_encounter_when_when_matches(self, tmp_path):
        result = runner.invoke(
            app,
            [
                "generate",
                "--patients", "30",
                "--seed", "42",
                "--module", "hypertension",
                "--out", str(tmp_path),
            ],
        )
        assert result.exit_code == 0, result.output

        for f in sorted(tmp_path.glob("*.json")):
            data = json.loads(f.read_text())
            entries = data["entry"]
            enc_entry = next(
                (e for e in entries if e["resource"]["resourceType"] == "Encounter"),
                None,
            )
            obs_entry = next(
                (e for e in entries if e["resource"]["resourceType"] == "Observation"),
                None,
            )
            if enc_entry and obs_entry:
                assert obs_entry["resource"]["encounter"]["reference"] == enc_entry["fullUrl"]

    def test_diabetes_default_when_today_unchanged(self, tmp_path):
        # Diabetes v0.3.0 doesn't declare `when` on its emits → defaults
        # to today. This ensures the new feature is fully backwards-
        # compatible with modules that don't opt in.
        result = runner.invoke(
            app,
            [
                "generate",
                "--patients", "30",
                "--seed", "42",
                "--module", "diabetes",
                "--out", str(tmp_path),
            ],
        )
        assert result.exit_code == 0, result.output

        for f in sorted(tmp_path.glob("*.json")):
            data = json.loads(f.read_text())
            cond = next(
                (e["resource"] for e in data["entry"] if e["resource"]["resourceType"] == "Condition"),
                None,
            )
            enc = next(
                (e["resource"] for e in data["entry"] if e["resource"]["resourceType"] == "Encounter"),
                None,
            )
            if not (cond and enc):
                continue
            onset = cond["onsetDateTime"]
            enc_start = enc["period"]["start"]
            # The diabetes module emits encounter with default `when: today`,
            # so the Encounter should be in the present, while the Condition
            # onset can be in the past.
            assert enc_start != onset or onset == date.today().isoformat(), (
                f"{f.name}: diabetes Encounter unexpectedly anchored to onset"
            )

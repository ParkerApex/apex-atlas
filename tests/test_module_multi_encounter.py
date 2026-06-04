"""Tests for multi-encounter conditions and explicit emit link_to."""

from __future__ import annotations

import json
import random
import textwrap
from datetime import date

from typer.testing import CliRunner

from parker_atlas.cli import app
from parker_atlas.modules import (
    EncounterEmit,
    SampledObservation,
    load_module_from_str,
    run_module,
)

runner = CliRunner()


def _two_encounter_module() -> str:
    return textwrap.dedent(
        """
        module: t
        version: 0.0.1
        conditions:
          - id: c
            code: {system: http://snomed.info/sct, code: "1", display: Foo}
            prevalence: {"0-99": 1.0}
            onset_age: {min: 25, max: 65}
            emits:
              - resource_type: Encounter
                spec_id: dx_visit
                when: onset
                encounter_class: AMB
                type: {system: s, code: dx, display: dx}
              - resource_type: Encounter
                spec_id: fu_visit
                when: today
                encounter_class: AMB
                type: {system: s, code: fu, display: fu}
              - resource_type: Observation
                spec_id: dx_bp
                when: onset
                link_to: dx_visit
                category: vital-signs
                code: {system: http://loinc.org, code: "85354-9", display: BP}
                components:
                  - code: {system: http://loinc.org, code: "8480-6", display: SBP}
                    value_range: {low: 140, high: 180, precision: 0}
                    unit: mm[Hg]
                  - code: {system: http://loinc.org, code: "8462-4", display: DBP}
                    value_range: {low: 90, high: 110, precision: 0}
                    unit: mm[Hg]
              - resource_type: Observation
                spec_id: fu_bp
                when: today
                link_to: fu_visit
                category: vital-signs
                code: {system: http://loinc.org, code: "85354-9", display: BP}
                components:
                  - code: {system: http://loinc.org, code: "8480-6", display: SBP}
                    value_range: {low: 120, high: 145, precision: 0}
                    unit: mm[Hg]
                  - code: {system: http://loinc.org, code: "8462-4", display: DBP}
                    value_range: {low: 75, high: 92, precision: 0}
                    unit: mm[Hg]
              - resource_type: MedicationRequest
                spec_id: med
                when: onset
                link_to: dx_visit
                medication: {system: rxnorm, code: "1", display: Drug}
        """
    )


class TestMultiEncounterParsing:
    def test_parses_two_encounters_with_link_to(self):
        mod = load_module_from_str(_two_encounter_module())
        cond = mod.conditions[0]
        encounters = [e for e in cond.emits if isinstance(e, EncounterEmit)]
        assert len(encounters) == 2
        # link_to fields are propagated
        obs_emits = [e for e in cond.emits if e.spec_id.endswith("_bp")]
        assert obs_emits[0].link_to == "dx_visit"
        assert obs_emits[1].link_to == "fu_visit"

    def test_default_link_to_is_none(self):
        mod = load_module_from_str(
            textwrap.dedent(
                """
                module: t
                version: 0.0.1
                conditions:
                  - id: c
                    code: {system: s, code: "1", display: d}
                    prevalence: {"0-99": 1.0}
                    emits:
                      - resource_type: Encounter
                        spec_id: visit
                        encounter_class: AMB
                        type: {system: s, code: c, display: d}
                      - resource_type: Observation
                        spec_id: o
                        category: vital-signs
                        code: {system: s, code: c, display: d}
                        value_range: {low: 1, high: 2}
                        unit: x
                """
            )
        )
        emits = mod.conditions[0].emits
        # Observation emit's link_to is None.
        obs_emit = next(e for e in emits if e.spec_id == "o")
        assert obs_emit.link_to is None


class TestMultiEncounterRuntime:
    def test_each_observation_carries_its_link_to(self):
        mod = load_module_from_str(_two_encounter_module())
        rng = random.Random(0)
        today = date(2026, 4, 25)
        diagnoses = run_module(mod, age_years=50, sex="female", rng=rng, today=today)
        srs = diagnoses[0].sampled_resources
        dx_bp = next(
            s for s in srs if isinstance(s, SampledObservation) and s.spec_id == "dx_bp"
        )
        fu_bp = next(
            s for s in srs if isinstance(s, SampledObservation) and s.spec_id == "fu_bp"
        )
        assert dx_bp.link_to == "dx_visit"
        assert fu_bp.link_to == "fu_visit"
        # And their dates differ — dx_bp at onset, fu_bp at today.
        assert dx_bp.effective_date != today
        assert fu_bp.effective_date == today


class TestMultiEncounterEndToEnd:
    def test_hypertension_v_0_6_emits_two_encounters(self, tmp_path):
        # The bundled hypertension v0.6.0 declares both htn_diagnosis_visit
        # and htn_followup_visit. Every hypertensive bundle should carry
        # both, with each Observation linked to the correct one.
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
        for f in sorted(tmp_path.glob("GPX-SYN-*.json")):
            data = json.loads(f.read_text())
            entries_by_type: dict[str, list[dict]] = {}
            for e in data["entry"]:
                entries_by_type.setdefault(e["resource"]["resourceType"], []).append(e)

            if "Condition" not in entries_by_type:
                continue
            assert len(entries_by_type.get("Encounter", [])) == 2, (
                f"{f.name}: expected exactly 2 Encounters, got "
                f"{len(entries_by_type.get('Encounter', []))}"
            )
            assert len(entries_by_type.get("Observation", [])) == 2, (
                f"{f.name}: expected exactly 2 Observations, got "
                f"{len(entries_by_type.get('Observation', []))}"
            )

            # Map Encounter type-display to entry for link assertions.
            enc_by_kind = {
                e["resource"]["type"][0]["text"]: e for e in entries_by_type["Encounter"]
            }
            assert "Encounter for check up" in enc_by_kind
            assert "Follow-up encounter" in enc_by_kind

            dx_url = enc_by_kind["Encounter for check up"]["fullUrl"]
            fu_url = enc_by_kind["Follow-up encounter"]["fullUrl"]

            obs_entries = entries_by_type["Observation"]
            # When onset_date < today (patient is old enough to fit the
            # 25-65 onset window), the diagnosis BP and follow-up BP have
            # different dates and we can pin links by date. Patients
            # younger than 25 have onset == today, so both observations
            # share the same date — skip that linking sub-check.
            today_str = date.today().isoformat()
            cond = entries_by_type["Condition"][0]["resource"]
            if cond["onsetDateTime"] != today_str:
                for o in obs_entries:
                    r = o["resource"]
                    ref = r["encounter"]["reference"]
                    eff = r["effectiveDateTime"]
                    if eff == today_str:
                        assert ref == fu_url, (
                            f"{f.name}: today's BP not linked to followup"
                        )
                    else:
                        assert ref == dx_url, (
                            f"{f.name}: diagnosis BP not linked to dx visit"
                        )

            examined += 1
        assert examined >= 1

    def test_medication_links_to_diagnosis_visit(self, tmp_path):
        result = runner.invoke(
            app,
            [
                "generate",
                "--patients", "50",
                "--seed", "42",
                "--module", "hypertension",
                "--out", str(tmp_path),
            ],
        )
        assert result.exit_code == 0, result.output

        for f in sorted(tmp_path.glob("GPX-SYN-*.json")):
            data = json.loads(f.read_text())
            meds = [
                e for e in data["entry"]
                if e["resource"]["resourceType"] == "MedicationRequest"
            ]
            if not meds:
                continue
            encounters = [
                e for e in data["entry"]
                if e["resource"]["resourceType"] == "Encounter"
            ]
            dx_visit = next(
                e for e in encounters
                if e["resource"]["type"][0]["text"] == "Encounter for check up"
            )
            for m in meds:
                assert m["resource"]["encounter"]["reference"] == dx_visit["fullUrl"]

    def test_single_encounter_modules_still_link_default(self, tmp_path):
        # diabetes / lipids / asthma / obesity each declare exactly one
        # Encounter with no link_to on their Observations / Medications.
        # The single-encounter fallback (auto-link if `when` matches)
        # should still wire them up.
        for module_name in ("diabetes", "hypercholesterolemia", "asthma"):
            out = tmp_path / module_name
            r = runner.invoke(
                app,
                [
                    "generate", "--patients", "30",
                    "--seed", "42", "--module", module_name,
                    "--out", str(out),
                ],
            )
            assert r.exit_code == 0, r.output
            for f in sorted(out.glob("GPX-SYN-*.json")):
                data = json.loads(f.read_text())
                meds = [
                    e for e in data["entry"]
                    if e["resource"]["resourceType"] == "MedicationRequest"
                ]
                encs = [
                    e for e in data["entry"]
                    if e["resource"]["resourceType"] == "Encounter"
                ]
                if meds and encs:
                    # Default-link fallback should fire (one Encounter, when matches).
                    assert meds[0]["resource"]["encounter"]["reference"] == encs[0]["fullUrl"]

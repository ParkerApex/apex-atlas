"""End-to-end tests for the Procedure emit path.

These exercise the full chain: module YAML declares a `Procedure` emit,
the runtime samples it, the CLI builds the FHIR Procedure resource, and
the structural validator + cohort harness recognize the resulting type.
"""

from __future__ import annotations

import json

import pytest
from fhir.resources.R4B.procedure import Procedure
from typer.testing import CliRunner

from parker_atlas.cli import app
from parker_atlas.modules.runtime import (
    ModuleError,
    load_module,
    load_module_from_str,
)

runner = CliRunner()

# Bundled procedure SNOMEDs.
ECHO_SNOMED = "40701008"
CATH_SNOMED = "41976001"
MRI_BRAIN_SNOMED = "698580004"


def _generate(tmp_path, *, modules: str, patients: int = 2000, seed: int = 42, fmt: str = "fhir-r4"):
    r = runner.invoke(
        app,
        [
            "generate",
            "--patients", str(patients),
            "--seed", str(seed),
            "--module", modules,
            "--format", fmt,
            "--out", str(tmp_path),
        ],
    )
    assert r.exit_code == 0, r.output


class TestProcedureDSLParsing:
    def test_procedure_emit_parses(self):
        yaml_text = """
module: test_proc
version: 0.1.0
conditions:
  - id: x
    code: {system: s, code: "1", display: x}
    prevalence: {"0-99": 1.0}
    emits:
      - resource_type: Procedure
        spec_id: x_echo
        code:
          system: http://snomed.info/sct
          code: "40701008"
          display: Echocardiography
"""
        module = load_module_from_str(yaml_text)
        assert len(module.conditions[0].emits) == 1

    def test_procedure_emit_missing_code_rejected(self):
        bad = """
module: test_proc
version: 0.1.0
conditions:
  - id: x
    code: {system: s, code: "1", display: x}
    prevalence: {"0-99": 1.0}
    emits:
      - resource_type: Procedure
        spec_id: x_echo
"""
        with pytest.raises(ModuleError, match="missing 'code'"):
            load_module_from_str(bad)


class TestBundledModulesEmitProcedures:
    @pytest.mark.parametrize(
        "module_name,expected_codes",
        [
            ("heart_failure", {ECHO_SNOMED}),
            ("ischemic_heart_disease", {CATH_SNOMED}),
            ("stroke", {MRI_BRAIN_SNOMED}),
        ],
    )
    def test_module_emits_expected_procedure(
        self, tmp_path, module_name, expected_codes
    ):
        _generate(tmp_path, modules=module_name, patients=3000)
        seen: set[str] = set()
        for f in tmp_path.glob("GPX-SYN-*.json"):
            data = json.loads(f.read_text())
            for entry in data["entry"]:
                r = entry["resource"]
                if r["resourceType"] != "Procedure":
                    continue
                for c in r["code"]["coding"]:
                    seen.add(c["code"])
        assert expected_codes <= seen, (
            f"{module_name}: expected procedures {expected_codes} not all seen "
            f"in cohort. Saw: {seen}"
        )


class TestProceduresAreValidFHIR:
    def test_each_procedure_round_trips(self, tmp_path):
        _generate(
            tmp_path,
            modules="heart_failure,ischemic_heart_disease,stroke",
            patients=500,
        )
        any_proc = False
        for f in tmp_path.glob("GPX-SYN-*.json"):
            data = json.loads(f.read_text())
            for entry in data["entry"]:
                r = entry["resource"]
                if r["resourceType"] == "Procedure":
                    Procedure.model_validate(r)
                    any_proc = True
        assert any_proc


class TestProcedureNDJSONOutput:
    def test_procedure_ndjson_file_created(self, tmp_path):
        _generate(
            tmp_path,
            modules="heart_failure",
            patients=2000,
            fmt="ndjson",
        )
        path = tmp_path / "Procedure.ndjson"
        assert path.exists(), "expected Procedure.ndjson when HF module is active"
        lines = [ln for ln in path.read_text().splitlines() if ln.strip()]
        # At 2000 HF-only patients (~3% baseline prevalence × 0.85 echo
        # probability), expect ~30-60 echocardiograms.
        assert len(lines) > 20


class TestStructuralValidatorAcceptsProcedures:
    def test_validate_passes_on_cohort_with_procedures(self, tmp_path):
        _generate(
            tmp_path,
            modules="heart_failure,ischemic_heart_disease",
            patients=200,
        )
        result = runner.invoke(app, ["validate", str(tmp_path)])
        assert result.exit_code == 0, result.output


class TestProcedureLinkingToEncounter:
    def test_procedure_links_to_diagnosis_encounter(self, tmp_path):
        # Procedures declared with `link_to: <encounter_spec_id>` should
        # carry an `encounter` reference pointing at the right Encounter.
        _generate(tmp_path, modules="heart_failure", patients=200)
        any_linked = False
        for f in tmp_path.glob("GPX-SYN-*.json"):
            data = json.loads(f.read_text())
            entries = data["entry"]
            encounter_urls = {
                e["fullUrl"]: e["resource"]
                for e in entries
                if e["resource"]["resourceType"] == "Encounter"
            }
            for e in entries:
                r = e["resource"]
                if r["resourceType"] != "Procedure":
                    continue
                if "encounter" in r:
                    ref = r["encounter"]["reference"]
                    assert ref in encounter_urls, (
                        f"Procedure encounter ref {ref} not present in bundle"
                    )
                    any_linked = True
        assert any_linked


class TestBundledHFLoadsCleanly:
    def test_hf_module_v_0_3_loads(self):
        # Sanity check that adding the procedure emit didn't break parse.
        load_module("heart_failure")
        load_module("ischemic_heart_disease")
        load_module("stroke")

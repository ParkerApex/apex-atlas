"""Tests for the SDoH comparison harness (scripts/sdoh_compare.py).

The script lives under scripts/ (not an installed package), so we load it by
path. Tests build tiny hand-crafted FHIR bundles so they're fast and exact.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "sdoh_compare.py"


@pytest.fixture(scope="module")
def mod():
    spec = importlib.util.spec_from_file_location("sdoh_compare", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _bundle(*resources):
    return {"resourceType": "Bundle", "entry": [{"resource": r} for r in resources]}


def _patient(pid):
    return {"resourceType": "Patient", "id": pid}


def _transport_positive():
    # transportation_barrier: question 93030-5, positive answer LA33-6
    return {
        "resourceType": "Observation",
        "code": {"coding": [{"system": "http://loinc.org", "code": "93030-5"}]},
        "valueCodeableConcept": {"coding": [{"code": "LA33-6"}]},
    }


def _amb():
    return {"resourceType": "Encounter", "class": {"code": "AMB"}}


def _med():
    return {"resourceType": "MedicationRequest"}


def test_positive_screen_and_counts(mod):
    res = [_patient("a"), _transport_positive(), _amb(), _amb(), _med()]
    assert mod._positive_screen_count(res, mod.DEFAULT_SCREENS) == 1
    assert mod._amb_encounters(res) == 2
    assert mod._med_requests(res) == 1


def test_no_false_positive_screen(mod):
    # An Observation with the question code but a NEGATIVE answer is not positive.
    neg = {
        "resourceType": "Observation",
        "code": {"coding": [{"code": "93030-5"}]},
        "valueCodeableConcept": {"coding": [{"code": "LA32-8"}]},  # "No"
    }
    assert mod._positive_screen_count([neg], mod.DEFAULT_SCREENS) == 0


def test_measure_cohort_and_slope(mod, tmp_path):
    # Burden-0 patients: 2 AMB each. Burden-1 patients: 1 AMB each → negative slope.
    (tmp_path / "p1.json").write_text(json.dumps(_bundle(_patient("1"), _amb(), _amb())))
    (tmp_path / "p2.json").write_text(json.dumps(_bundle(_patient("2"), _amb(), _amb())))
    (tmp_path / "p3.json").write_text(json.dumps(
        _bundle(_patient("3"), _transport_positive(), _amb())))
    (tmp_path / "p4.json").write_text(json.dumps(
        _bundle(_patient("4"), _transport_positive(), _amb())))

    res = mod.measure_cohort(tmp_path, mod.DEFAULT_SCREENS)
    assert res["total"] == 4
    assert res["any_screen"] == 2
    rows, slope = mod._cohort_rows(res["buckets"])
    # burden 0 → mean 2.0 AMB; burden 1 → mean 1.0 → slope -50%
    assert slope == pytest.approx(-0.5)


def test_render_runs(mod, tmp_path):
    (tmp_path / "p.json").write_text(json.dumps(_bundle(_patient("1"), _amb())))
    res = {"atlas": mod.measure_cohort(tmp_path, mod.DEFAULT_SCREENS)}
    md = mod._render(res, mod.DEFAULT_SCREENS)
    assert "SDoH causal-signal comparison" in md
    assert "## atlas" in md

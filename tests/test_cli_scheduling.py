"""Tests for `atlas publish-scheduling`."""

from __future__ import annotations

import json

from fhir.resources.R4B.slot import Slot
from typer.testing import CliRunner

from parker_atlas.cli import app

runner = CliRunner()


def _lines(path):
    return [json.loads(ln) for ln in path.read_text().splitlines() if ln.strip()]


class TestPublishScheduling:
    def test_writes_manifest_and_ndjson(self, tmp_path):
        out = tmp_path / "scheduling"
        result = runner.invoke(
            app,
            [
                "publish-scheduling",
                "--sites", "2",
                "--weeks", "1",
                "--seed", "1",
                "--window-start", "2026-07-13",
                "--out", str(out),
            ],
        )
        assert result.exit_code == 0, result.output
        manifest = json.loads((out / "bulk-publish-manifest.json").read_text())
        assert [o["type"] for o in manifest["output"]] == ["Location", "Schedule", "Slot"]
        slots = _lines(out / "Slot.ndjson")
        assert slots
        Slot(**slots[0])
        # No patients passed → no Appointment file.
        assert not (out / "Appointment.ndjson").exists()

    def test_books_appointments_from_patient_file(self, tmp_path):
        patients = tmp_path / "Patient.ndjson"
        patients.write_text(
            "\n".join(
                json.dumps({"resourceType": "Patient", "id": f"GPX-SYN-000000000{i}-8"})
                for i in range(1, 4)
            )
            + "\n"
        )
        out = tmp_path / "scheduling"
        result = runner.invoke(
            app,
            [
                "publish-scheduling",
                "--sites", "2",
                "--weeks", "1",
                "--seed", "3",
                "--booked-fraction", "0.5",
                "--patients", str(patients),
                "--out", str(out),
            ],
        )
        assert result.exit_code == 0, result.output
        appts = _lines(out / "Appointment.ndjson")
        assert appts
        pool = {f"GPX-SYN-000000000{i}-8" for i in range(1, 4)}
        for a in appts:
            ref = next(
                p["actor"]["reference"]
                for p in a["participant"]
                if p["actor"]["reference"].startswith("Patient/")
            )
            assert ref.split("/", 1)[1] in pool

    def test_bad_service_type_exits_nonzero(self, tmp_path):
        result = runner.invoke(
            app,
            ["publish-scheduling", "--service-types", "nope", "--out", str(tmp_path / "s")],
        )
        assert result.exit_code == 1
        assert "unknown service type" in result.output

    def test_missing_patient_file_exits_nonzero(self, tmp_path):
        result = runner.invoke(
            app,
            ["publish-scheduling", "--patients", str(tmp_path / "missing.ndjson")],
        )
        assert result.exit_code == 1

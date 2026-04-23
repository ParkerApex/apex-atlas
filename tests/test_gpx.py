"""Tests for the Parker GPX identifier implementation."""

from __future__ import annotations

import pytest

from parker_atlas.gpx import (
    MAX_NUMERIC,
    SYSTEM_URI,
    Allocator,
    Category,
    GPX,
    GPXError,
    compute_check_digit,
)


class TestCheckDigit:
    """Verify the Luhn mod 10 implementation matches the spec worked example."""

    def test_spec_worked_example(self):
        # Parker GPX Specification v1.0 §4.2 worked example
        assert compute_check_digit("0000000001") == "8"

    def test_canonical_examples_from_spec(self):
        # All other examples given in the spec
        assert compute_check_digit("0000000042") == "2"
        assert compute_check_digit("0000000500") == "9"

    def test_rejects_non_digit_input(self):
        with pytest.raises(GPXError):
            compute_check_digit("000000000A")

    def test_rejects_wrong_length(self):
        with pytest.raises(GPXError):
            compute_check_digit("12345")
        with pytest.raises(GPXError):
            compute_check_digit("00000000001")

    def test_check_digit_is_stable(self):
        # Same input always produces same output
        for _ in range(100):
            assert compute_check_digit("1234567890") == compute_check_digit("1234567890")

    def test_single_digit_errors_are_detected(self):
        # Luhn catches all single-digit errors
        original = "1234567890"
        correct_cd = compute_check_digit(original)
        for pos in range(10):
            for new_digit in "0123456789":
                if new_digit == original[pos]:
                    continue
                corrupted = original[:pos] + new_digit + original[pos + 1 :]
                assert compute_check_digit(corrupted) != correct_cd


class TestGPXConstruction:
    def test_mint_produces_valid_identifier(self):
        gpx = GPX.mint(Category.SYNTHETIC, 1)
        assert str(gpx) == "GPX-SYN-0000000001-8"
        assert gpx.is_valid()

    def test_mint_production_has_no_prefix(self):
        gpx = GPX.mint(Category.PRODUCTION, 1)
        assert str(gpx) == "GPX-0000000001-8"

    def test_mint_rejects_zero(self):
        with pytest.raises(GPXError):
            GPX.mint(Category.SYNTHETIC, 0)

    def test_mint_rejects_overflow(self):
        with pytest.raises(GPXError):
            GPX.mint(Category.SYNTHETIC, MAX_NUMERIC + 1)

    def test_mint_accepts_max(self):
        gpx = GPX.mint(Category.SYNTHETIC, MAX_NUMERIC)
        assert gpx.numeric == "9999999999"
        assert gpx.is_valid()


class TestGPXParsing:
    def test_parse_production(self):
        gpx = GPX.parse("GPX-0000000001-8")
        assert gpx.category is Category.PRODUCTION
        assert gpx.numeric == "0000000001"

    def test_parse_synthetic(self):
        gpx = GPX.parse("GPX-SYN-0000000001-8")
        assert gpx.category is Category.SYNTHETIC

    def test_parse_all_categories(self):
        assert GPX.parse("GPX-SYN-0000000042-2").category is Category.SYNTHETIC
        assert GPX.parse("GPX-TST-0000000042-2").category is Category.TEST
        assert GPX.parse("GPX-DEM-0000000042-2").category is Category.DEMO
        assert GPX.parse("GPX-DEV-0000000042-2").category is Category.DEVELOPER

    def test_parse_rejects_malformed(self):
        bad_values = [
            "",
            "GPX",
            "GPX-0000000001",          # missing check digit
            "gpx-0000000001-8",         # lowercase
            "GPX-XYZ-0000000001-8",     # unknown prefix
            "GPX-0000000000-0",         # reserved all-zero
            "GPX-000000001-8",          # 9 digits
            "GPX-00000000001-8",        # 11 digits
            "GPX SYN 0000000001 8",     # spaces instead of hyphens
        ]
        for bad in bad_values:
            with pytest.raises(GPXError):
                GPX.parse(bad)

    def test_parse_rejects_bad_check_digit(self):
        with pytest.raises(GPXError, match="check digit mismatch"):
            GPX.parse("GPX-SYN-0000000001-7")  # should be 8

    def test_parse_rejects_non_string(self):
        with pytest.raises(GPXError):
            GPX.parse(12345)  # type: ignore[arg-type]

    def test_round_trip(self):
        for n in [1, 42, 500, 9999, 123456789, MAX_NUMERIC]:
            gpx = GPX.mint(Category.SYNTHETIC, n)
            reparsed = GPX.parse(str(gpx))
            assert reparsed == gpx


class TestCategory:
    def test_only_production_is_phi(self):
        assert Category.PRODUCTION.is_phi
        assert not Category.SYNTHETIC.is_phi
        assert not Category.TEST.is_phi
        assert not Category.DEMO.is_phi
        assert not Category.DEVELOPER.is_phi


class TestFHIREncoding:
    def test_to_fhir_identifier_synthetic(self):
        gpx = GPX.mint(Category.SYNTHETIC, 1)
        identifier = gpx.to_fhir_identifier()

        assert identifier["use"] == "official"
        assert identifier["system"] == SYSTEM_URI
        assert identifier["system"] == "https://parkerapex.com/gpx"
        assert identifier["value"] == "GPX-SYN-0000000001-8"
        assert identifier["assigner"]["display"] == "Parker Atlas Synthetic Population"

    def test_to_fhir_identifier_production(self):
        gpx = GPX.mint(Category.PRODUCTION, 1)
        identifier = gpx.to_fhir_identifier()
        assert identifier["value"] == "GPX-0000000001-8"
        assert identifier["assigner"]["display"] == "Parker Health Global Patient Registry"

    def test_without_assigner(self):
        gpx = GPX.mint(Category.SYNTHETIC, 1)
        identifier = gpx.to_fhir_identifier(include_assigner=False)
        assert "assigner" not in identifier

    def test_htest_tag(self):
        tag = GPX.synthetic_meta_tag()
        assert tag["system"] == "http://terminology.hl7.org/CodeSystem/v3-ActReason"
        assert tag["code"] == "HTEST"


class TestAllocator:
    def test_sequential_allocation(self):
        alloc = Allocator(Category.SYNTHETIC)
        first = alloc.allocate()
        second = alloc.allocate()
        assert first.numeric == "0000000001"
        assert second.numeric == "0000000002"

    def test_batch_allocation(self):
        alloc = Allocator(Category.SYNTHETIC)
        batch = alloc.allocate_batch(5)
        assert len(batch) == 5
        assert [g.numeric for g in batch] == [
            "0000000001",
            "0000000002",
            "0000000003",
            "0000000004",
            "0000000005",
        ]

    def test_allocator_rejects_production(self):
        with pytest.raises(GPXError, match="must not mint production"):
            Allocator(Category.PRODUCTION)

    def test_start_offset(self):
        alloc = Allocator(Category.SYNTHETIC, start=100)
        assert alloc.allocate().numeric == "0000000101"

    def test_exhaustion_raises(self):
        alloc = Allocator(Category.SYNTHETIC, start=MAX_NUMERIC - 1)
        alloc.allocate()  # MAX_NUMERIC
        with pytest.raises(GPXError, match="exhausted"):
            alloc.allocate()

    def test_batch_overflow_raises(self):
        alloc = Allocator(Category.SYNTHETIC, start=MAX_NUMERIC - 2)
        with pytest.raises(GPXError, match="exceed counter ceiling"):
            alloc.allocate_batch(5)

    def test_all_allocated_ids_are_unique(self):
        alloc = Allocator(Category.SYNTHETIC)
        batch = alloc.allocate_batch(1000)
        assert len({str(g) for g in batch}) == 1000


class TestFileAllocator:
    def test_persists_across_instances(self, tmp_path):
        from parker_atlas.gpx import FileAllocator

        state = tmp_path / "counter.state"

        alloc1 = FileAllocator(Category.SYNTHETIC, state)
        g1 = alloc1.allocate()
        g2 = alloc1.allocate()

        # Fresh allocator, same state file
        alloc2 = FileAllocator(Category.SYNTHETIC, state)
        g3 = alloc2.allocate()

        assert g1.numeric == "0000000001"
        assert g2.numeric == "0000000002"
        assert g3.numeric == "0000000003"

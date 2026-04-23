"""
Parker GPX Identifier — allocation, formatting, and validation.

Implements the Parker GPX Identifier Specification v1.0
(https://parkerapex.com/gpx).

A GPX identifier uniquely identifies a patient across the Parker ecosystem.
This module is the reference implementation used by Parker Atlas to mint
synthetic patient identifiers under the SYN prefix namespace.

Format:  GPX[-PREFIX]-NNNNNNNNNN-C
  - Optional 3-letter prefix (SYN | TST | DEM | DEV); absence = production
  - 10-digit zero-padded sequential numeric portion
  - Single-digit Luhn mod 10 check digit

Example:
    >>> gpx = GPX.allocate(Category.SYNTHETIC)
    >>> str(gpx)
    'GPX-SYN-0000000001-8'
    >>> GPX.parse('GPX-SYN-0000000001-8').is_valid()
    True
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class Category(str, Enum):
    """GPX prefix categories as defined in the Parker GPX Specification v1.0."""

    PRODUCTION = ""      # No prefix — real clinical data
    SYNTHETIC = "SYN"    # Parker Atlas generated data
    TEST = "TST"         # Internal QA environments
    DEMO = "DEM"         # Sales demos
    DEVELOPER = "DEV"    # Developer sandbox

    @property
    def is_phi(self) -> bool:
        """Only the production category may contain PHI."""
        return self is Category.PRODUCTION

    @property
    def display(self) -> str:
        return {
            Category.PRODUCTION: "Production",
            Category.SYNTHETIC: "Synthetic",
            Category.TEST: "Test",
            Category.DEMO: "Demo",
            Category.DEVELOPER: "Developer",
        }[self]


# Compiled validation expression — matches format only, does not verify check digit.
_GPX_RE = re.compile(r"^GPX(-(SYN|TST|DEM|DEV))?-(?!0{10})([0-9]{10})-([0-9])$")

# The canonical FHIR system URI for all GPX identifiers.
SYSTEM_URI = "https://parkerapex.com/gpx"

# Reserved numeric value — never allocated.
RESERVED_ZERO = "0000000000"

# Counter exhaustion ceiling.
MAX_NUMERIC = 9_999_999_999


class GPXError(ValueError):
    """Raised when a GPX value is malformed or fails validation."""


def compute_check_digit(numeric: str) -> str:
    """
    Compute the Luhn mod 10 check digit for a ten-digit numeric portion.

    Normative per Parker GPX Specification v1.0 §4.

    Args:
        numeric: Ten-digit zero-padded decimal string.

    Returns:
        Single-character decimal check digit.

    Raises:
        GPXError: If the input is not a ten-digit decimal string.
    """
    if len(numeric) != 10 or not numeric.isdigit():
        raise GPXError(f"numeric portion must be exactly 10 digits, got {numeric!r}")

    total = 0
    for i, ch in enumerate(reversed(numeric)):
        n = int(ch)
        if i % 2 == 0:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return str((10 - (total % 10)) % 10)


@dataclass(frozen=True, slots=True)
class GPX:
    """An immutable, validated Parker Global Patient Identifier."""

    category: Category
    numeric: str          # Ten-digit zero-padded
    check_digit: str      # Single decimal digit

    # -- Construction -------------------------------------------------------

    @classmethod
    def mint(cls, category: Category, value: int) -> GPX:
        """
        Mint a GPX from a raw integer value. Used by the allocator.

        Prefer `Allocator.allocate()` over calling this directly.
        """
        if not 1 <= value <= MAX_NUMERIC:
            raise GPXError(
                f"value must be between 1 and {MAX_NUMERIC}, got {value}"
            )
        numeric = str(value).zfill(10)
        return cls(
            category=category,
            numeric=numeric,
            check_digit=compute_check_digit(numeric),
        )

    @classmethod
    def parse(cls, value: str) -> GPX:
        """
        Parse and fully validate a GPX string, including the check digit.

        Raises GPXError if the value is malformed or the check digit is wrong.
        """
        if not isinstance(value, str):
            raise GPXError(f"GPX must be a string, got {type(value).__name__}")

        match = _GPX_RE.match(value)
        if not match:
            raise GPXError(f"malformed GPX: {value!r}")

        prefix_group, numeric, provided_check = match.group(2), match.group(3), match.group(4)
        category = Category(prefix_group or "")

        expected_check = compute_check_digit(numeric)
        if provided_check != expected_check:
            raise GPXError(
                f"check digit mismatch for {value!r}: "
                f"expected {expected_check}, got {provided_check}"
            )

        return cls(category=category, numeric=numeric, check_digit=provided_check)

    # -- Serialization ------------------------------------------------------

    def __str__(self) -> str:
        prefix = f"-{self.category.value}" if self.category.value else ""
        return f"GPX{prefix}-{self.numeric}-{self.check_digit}"

    def __repr__(self) -> str:
        return f"GPX({self!s})"

    # -- Validation ---------------------------------------------------------

    def is_valid(self) -> bool:
        """Re-verify self-consistency. Always True for instances minted correctly."""
        return compute_check_digit(self.numeric) == self.check_digit

    # -- FHIR ---------------------------------------------------------------

    def to_fhir_identifier(self, include_assigner: bool = True) -> dict:
        """
        Produce a FHIR Identifier element referencing this GPX.

        Returns a dict suitable for inclusion in Patient.identifier or any
        resource reference using identifier-based Reference.
        """
        identifier: dict = {
            "use": "official",
            "system": SYSTEM_URI,
            "value": str(self),
        }
        if include_assigner:
            identifier["assigner"] = {
                "display": self._assigner_display(),
            }
        return identifier

    def _assigner_display(self) -> str:
        return {
            Category.PRODUCTION: "Parker Health Global Patient Registry",
            Category.SYNTHETIC: "Parker Atlas Synthetic Population",
            Category.TEST: "Parker Test Environment",
            Category.DEMO: "Parker Demo Environment",
            Category.DEVELOPER: "Parker Developer Sandbox",
        }[self.category]

    @staticmethod
    def synthetic_meta_tag() -> dict:
        """
        Return the HL7 v3 ActReason HTEST tag for marking a resource as
        synthetic. Required on all Parker Atlas output per Spec §6.3.
        """
        return {
            "system": "http://terminology.hl7.org/CodeSystem/v3-ActReason",
            "code": "HTEST",
            "display": "test health data",
        }


# ---------------------------------------------------------------------------
# Allocator
# ---------------------------------------------------------------------------


class Allocator:
    """
    Sequential GPX allocator with durable persistence of the high-water mark.

    For Parker Atlas, the allocator is process-local and backed by a simple
    state file. For production APEX, this is replaced with a centralized
    sequence service (not included in this open-source distribution).

    Thread-safe within a single process. Not safe across multiple processes
    unless backed by a shared state file with OS-level file locking — see
    `FileAllocator` for a minimal cross-process implementation.
    """

    def __init__(self, category: Category, start: int = 0) -> None:
        if category is Category.PRODUCTION:
            raise GPXError(
                "Parker Atlas allocator must not mint production GPX values. "
                "Use a category with a non-empty prefix (SYN, TST, DEM, DEV)."
            )
        self._category = category
        self._counter = start
        self._lock = threading.Lock()

    @property
    def category(self) -> Category:
        return self._category

    @property
    def current(self) -> int:
        return self._counter

    def allocate(self) -> GPX:
        """Allocate the next sequential GPX in this category."""
        with self._lock:
            self._counter += 1
            if self._counter > MAX_NUMERIC:
                raise GPXError(
                    f"{self._category.display} GPX counter exhausted "
                    f"(reached {MAX_NUMERIC}). Specification revision required."
                )
            return GPX.mint(self._category, self._counter)

    def allocate_batch(self, n: int) -> list[GPX]:
        """Allocate n sequential GPX values atomically."""
        if n < 1:
            raise ValueError("batch size must be >= 1")
        with self._lock:
            if self._counter + n > MAX_NUMERIC:
                raise GPXError(
                    f"batch of {n} would exceed counter ceiling "
                    f"({self._counter} + {n} > {MAX_NUMERIC})"
                )
            result = [
                GPX.mint(self._category, self._counter + i + 1)
                for i in range(n)
            ]
            self._counter += n
            return result


class FileAllocator(Allocator):
    """
    Allocator that persists the counter to a local file between runs.

    Suitable for single-host Atlas generation. Not intended for distributed
    or highly concurrent workloads; for those, implement a backend using a
    database sequence or a consensus-backed counter.
    """

    def __init__(self, category: Category, state_path: Path) -> None:
        self._state_path = Path(state_path)
        start = self._load()
        super().__init__(category, start=start)

    def _load(self) -> int:
        if not self._state_path.exists():
            return 0
        try:
            return int(self._state_path.read_text().strip())
        except (OSError, ValueError) as exc:
            raise GPXError(
                f"cannot read allocator state from {self._state_path}: {exc}"
            ) from exc

    def _persist(self) -> None:
        tmp = self._state_path.with_suffix(".tmp")
        tmp.write_text(str(self._counter))
        tmp.replace(self._state_path)

    def allocate(self) -> GPX:
        gpx = super().allocate()
        self._persist()
        return gpx

    def allocate_batch(self, n: int) -> list[GPX]:
        batch = super().allocate_batch(n)
        self._persist()
        return batch

"""
Parker GPX Identifier — allocation, formatting, and validation.

Implements the Parker GPX Identifier Specification v1.0
(https://parkerapex.com/gpx).

A GPX identifier uniquely identifies a patient across the APEX ecosystem.
This module is the reference implementation used by APEX Atlas to mint
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

import fcntl
import os
import re
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class Category(str, Enum):
    """GPX prefix categories as defined in the Parker GPX Specification v1.0."""

    PRODUCTION = ""      # No prefix — real clinical data
    SYNTHETIC = "SYN"    # APEX Atlas generated data
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
            Category.SYNTHETIC: "APEX Atlas Synthetic Population",
            Category.TEST: "Parker Test Environment",
            Category.DEMO: "Parker Demo Environment",
            Category.DEVELOPER: "Parker Developer Sandbox",
        }[self.category]

    @staticmethod
    def synthetic_meta_tag() -> dict:
        """
        Return the HL7 v3 ActReason HTEST tag for marking a resource as
        synthetic. Required on all APEX Atlas output per Spec §6.3.
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

    For APEX Atlas, the allocator is process-local and backed by a simple
    state file. For production APEX, this is replaced with a centralized
    sequence service (not included in this open-source distribution).

    Thread-safe within a single process. Not safe across multiple processes
    unless backed by a shared state file with OS-level file locking — see
    `FileAllocator` for a minimal cross-process implementation.
    """

    def __init__(self, category: Category, start: int = 0) -> None:
        if category is Category.PRODUCTION:
            raise GPXError(
                "APEX Atlas allocator must not mint production GPX values. "
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
    Allocator that persists the counter to a local state file and coordinates
    across concurrent processes using an advisory file lock (`fcntl.flock`).

    Durability guarantees (POSIX):
    - On each allocation, the counter is re-read from disk under an exclusive
      lock, incremented, written to a temp file, fsynced, atomically renamed
      over the state file, and the parent directory is fsynced. A crash after
      a successful allocate leaves the state file containing the allocated
      value.
    - An OS-level exclusive flock on a sibling `.lock` file serializes
      allocators running in different processes on the same host, so two
      processes cannot mint the same GPX.

    Not safe across hosts (NFS flock semantics are unreliable) or against
    distributed workloads; use a centralized sequence service in that case.

    Requires a POSIX-like platform. Windows is not supported.
    """

    def __init__(self, category: Category, state_path: Path) -> None:
        if category is Category.PRODUCTION:
            raise GPXError(
                "APEX Atlas allocator must not mint production GPX values. "
                "Use a category with a non-empty prefix (SYN, TST, DEM, DEV)."
            )
        self._category = category
        self._state_path = Path(state_path)
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        # Lock file lives alongside the state file and is never renamed, so
        # its inode is stable for the lifetime of concurrent allocators.
        self._lock_path = self._state_path.with_name(self._state_path.name + ".lock")
        self._thread_lock = threading.Lock()

    @property
    def category(self) -> Category:
        return self._category

    @property
    def current(self) -> int:
        with self._thread_lock, self._file_lock():
            return self._read_counter()

    @contextmanager
    def _file_lock(self) -> Iterator[None]:
        fd = os.open(self._lock_path, os.O_WRONLY | os.O_CREAT, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)

    def _read_counter(self) -> int:
        if not self._state_path.exists():
            return 0
        try:
            return int(self._state_path.read_text().strip())
        except (OSError, ValueError) as exc:
            raise GPXError(
                f"cannot read allocator state from {self._state_path}: {exc}"
            ) from exc

    def _write_counter(self, value: int) -> None:
        tmp_path = self._state_path.with_name(self._state_path.name + ".tmp")
        fd = os.open(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
        try:
            os.write(fd, str(value).encode("ascii"))
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(tmp_path, self._state_path)
        # fsync the directory so the rename itself is durable on crash.
        dir_fd = os.open(self._state_path.parent, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)

    def allocate(self) -> GPX:
        with self._thread_lock, self._file_lock():
            current = self._read_counter()
            new_value = current + 1
            if new_value > MAX_NUMERIC:
                raise GPXError(
                    f"{self._category.display} GPX counter exhausted "
                    f"(reached {MAX_NUMERIC}). Specification revision required."
                )
            self._write_counter(new_value)
            return GPX.mint(self._category, new_value)

    def allocate_batch(self, n: int) -> list[GPX]:
        if n < 1:
            raise ValueError("batch size must be >= 1")
        with self._thread_lock, self._file_lock():
            current = self._read_counter()
            if current + n > MAX_NUMERIC:
                raise GPXError(
                    f"batch of {n} would exceed counter ceiling "
                    f"({current} + {n} > {MAX_NUMERIC})"
                )
            batch = [
                GPX.mint(self._category, current + i + 1) for i in range(n)
            ]
            self._write_counter(current + n)
            return batch

"""
Parker Atlas — a next-generation synthetic FHIR patient population generator.

See https://github.com/parker-health/parker-atlas for documentation.
"""

from parker_atlas.gpx import (
    SYSTEM_URI,
    Allocator,
    Category,
    FileAllocator,
    GPX,
    GPXError,
    compute_check_digit,
)

__version__ = "0.1.0"

__all__ = [
    "GPX",
    "GPXError",
    "Category",
    "Allocator",
    "FileAllocator",
    "SYSTEM_URI",
    "compute_check_digit",
    "__version__",
]

"""SMART Scheduling Links (`$bulk-publish`) dataset generation.

Public API for generating and serializing synthetic appointment-availability
datasets that conform to the SMART Scheduling Links specification
(https://github.com/smart-on-fhir/smart-scheduling-links).
"""

from parker_atlas.scheduling.links import (
    CLINIC_SITES,
    DEFAULT_SERVICE_KEYS,
    SERVICE_TYPES,
    ClinicSite,
    SchedulingConfig,
    SchedulingDataset,
    ServiceType,
    generate_scheduling_dataset,
)
from parker_atlas.scheduling.publish import build_manifest, write_bulk_publish

__all__ = [
    "CLINIC_SITES",
    "DEFAULT_SERVICE_KEYS",
    "SERVICE_TYPES",
    "ClinicSite",
    "SchedulingConfig",
    "SchedulingDataset",
    "ServiceType",
    "build_manifest",
    "generate_scheduling_dataset",
    "write_bulk_publish",
]

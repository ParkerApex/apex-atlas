"""
Cross-file referential-integrity validation.

Scans a directory (or file) of FHIR output — NDJSON bulk exports, SMART
Scheduling Links / Plan-Net ``$bulk-publish`` datasets, or R4 Bundles — and
checks that every literal reference resolves to a resource present in the same
dataset.

Resolution index:
- every resource is indexed by its relative ``ResourceType/id`` reference, and
- every Bundle entry is additionally indexed by its ``fullUrl``.

References classified as external are not flagged: absolute ``http(s)://`` URLs,
contained ``#fragment`` references, and (with a hint) ``urn:uuid:`` references
that aren't a known Bundle fullUrl — those only resolve within a transaction
Bundle or a relative-reference export (``atlas generate --ref-style relative``).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_SKIP_JSON_STEMS = {"generation-metadata", "parquet-schema", "bulk-publish-manifest"}


@dataclass(frozen=True, slots=True)
class DanglingReference:
    file: str
    source: str      # "ResourceType/id" of the referring resource
    reference: str   # the unresolved reference value


@dataclass(slots=True)
class RefReport:
    resources_scanned: int = 0
    references_total: int = 0
    resolved: int = 0
    dangling: list[DanglingReference] = field(default_factory=list)
    urn_uuid_unresolved: int = 0     # urn:uuid refs not found (needs Bundle/relative)
    files_scanned: int = 0
    parse_errors: list[tuple[str, str]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.dangling and self.urn_uuid_unresolved == 0


def _iter_references(node: Any):
    """Yield every string Reference.reference value in a resource."""
    if isinstance(node, dict):
        ref = node.get("reference")
        if isinstance(ref, str):
            yield ref
        for value in node.values():
            yield from _iter_references(value)
    elif isinstance(node, list):
        for value in node:
            yield from _iter_references(value)


def _resource_key(resource: dict) -> str | None:
    rtype, rid = resource.get("resourceType"), resource.get("id")
    if rtype and rid:
        return f"{rtype}/{rid}"
    return None


def _load(path: Path) -> tuple[list[tuple[Path, dict]], set[str], list[tuple[str, str]]]:
    """Return (referring resources, resolvable-target index, parse errors)."""
    resources: list[tuple[Path, dict]] = []
    index: set[str] = set()
    errors: list[tuple[str, str]] = []

    files = (
        [path]
        if path.is_file()
        else sorted([*path.rglob("*.ndjson"), *path.rglob("*.json")])
    )

    for f in files:
        if f.suffix == ".json" and f.stem in _SKIP_JSON_STEMS:
            continue
        try:
            if f.suffix == ".ndjson":
                for line in f.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line:
                        _register(f, json.loads(line), resources, index)
            else:
                doc = json.loads(f.read_text(encoding="utf-8"))
                if isinstance(doc, list):
                    # A JSON array of resources (e.g. pretty-printed examples).
                    for item in doc:
                        if isinstance(item, dict) and "resourceType" in item:
                            _register(f, item, resources, index)
                elif isinstance(doc, dict) and doc.get("resourceType") == "Bundle":
                    for entry in doc.get("entry", []):
                        full_url = entry.get("fullUrl")
                        if isinstance(full_url, str):
                            index.add(full_url)
                        res = entry.get("resource")
                        if isinstance(res, dict):
                            _register(f, res, resources, index)
                elif isinstance(doc, dict) and "resourceType" in doc:
                    _register(f, doc, resources, index)
        except (json.JSONDecodeError, OSError) as exc:
            errors.append((str(f), str(exc)))

    return resources, index, errors


def _register(
    f: Path, resource: dict, resources: list[tuple[Path, dict]], index: set[str]
) -> None:
    key = _resource_key(resource)
    if key:
        index.add(key)
    resources.append((f, resource))


def validate_references(path: Path) -> RefReport:
    """Check that every literal reference in ``path`` resolves within the dataset."""
    resources, index, errors = _load(path)
    report = RefReport(parse_errors=errors)
    report.resources_scanned = len(resources)
    report.files_scanned = len({str(f) for f, _ in resources})

    for f, resource in resources:
        source = _resource_key(resource) or resource.get("resourceType", "?")
        for ref in _iter_references(resource):
            if ref.startswith("#") or ref.startswith(("http://", "https://")):
                continue  # contained or external — not a same-dataset target
            report.references_total += 1
            if ref in index:
                report.resolved += 1
            elif ref.startswith("urn:uuid:"):
                report.urn_uuid_unresolved += 1
                report.dangling.append(DanglingReference(str(f), source, ref))
            else:
                report.dangling.append(DanglingReference(str(f), source, ref))

    return report

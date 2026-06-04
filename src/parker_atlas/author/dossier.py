"""
The research dossier — the audited input to module synthesis.

A dossier is the structured, fully-cited result of a deep-research pass on one
clinical condition. It is the artifact a clinician reviews and signs off on.
Synthesis (`synthesize.py`) turns it deterministically into a draft module and
a draft fidelity expectation.

The contract this loader enforces — and the reason the dossier exists as a
distinct schema rather than raw module YAML — is **no uncited numbers**. Every
numeric claim must carry a citation:

- the prevalence cells (one citation for the table),
- each observation's `value_range`,
- each medication's `fraction`,
- each progression's `probability`.

A dossier that asserts a rate without a source fails to load. Structural FHIR
validity (valid codes, link_to wiring, bracket syntax) is *not* re-checked
here — that is the job of the real loaders during synthesis round-trip, and
duplicating it would let the two drift. This loader owns provenance; the
runtime loaders own structure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import yaml

from parker_atlas.fhir.observation import SUPPORTED_CATEGORIES as OBSERVATION_CATEGORIES

SNOMED_SYSTEM = "http://snomed.info/sct"
LOINC_SYSTEM = "http://loinc.org"

ALLOWED_STRATIFY = ("age_bracket", "sex_and_age")
ALLOWED_METHODS = ("deep-research-skill", "web_search", "manual")
SEX_KEYS = ("female", "male")


class DossierError(ValueError):
    """Raised when a research dossier is malformed or has an uncited number."""


@dataclass(frozen=True, slots=True)
class Dossier:
    """A validated research dossier.

    Holds the structured fields synthesis needs plus the raw mapping (so the
    CLI can write the dossier back out into the draft directory verbatim for
    the audit trail).
    """

    condition: str
    version: str
    generated: dict[str, Any]
    snomed: dict[str, str]
    icd10: list[dict[str, str]]
    prevalence_stratify_by: str
    prevalence_cells: dict[str, Any]
    prevalence_citation: dict[str, str]
    onset_min: int
    onset_max: int
    encounters: list[dict[str, Any]]
    observations: list[dict[str, Any]]
    medications: list[dict[str, Any]]
    progressions: list[dict[str, Any]]
    notes: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def all_citations(self) -> list[dict[str, str]]:
        """Every distinct citation in the dossier, prevalence first.

        Deduplicated by (source, url) and rendered in the {source, url,
        summary} shape the module `cites:` block expects.
        """
        seen: set[tuple[str, str]] = set()
        out: list[dict[str, str]] = []
        for cit in [self.prevalence_citation, *self._clinical_citations()]:
            if not cit:
                continue
            key = (str(cit.get("source", "")), str(cit.get("url", "")))
            if key in seen:
                continue
            seen.add(key)
            out.append(
                {
                    "source": str(cit.get("source", "")),
                    "url": str(cit.get("url", "")),
                    "summary": str(cit.get("summary", cit.get("note", ""))),
                }
            )
        return out

    def _clinical_citations(self) -> list[dict[str, str]]:
        cits: list[dict[str, str]] = []
        for group in (self.observations, self.medications, self.progressions):
            for item in group:
                cit = item.get("citation")
                if cit:
                    cits.append(cit)
        return cits


# -- Loading -----------------------------------------------------------------


def load_dossier_from_str(yaml_text: str) -> Dossier:
    """Parse and validate a dossier YAML string into a Dossier."""
    try:
        data = yaml.safe_load(yaml_text)
    except yaml.YAMLError as exc:
        raise DossierError(f"invalid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise DossierError("dossier must be a mapping at the top level")

    for required in ("condition", "codes", "prevalence", "onset_age"):
        if required not in data:
            raise DossierError(f"missing required key: {required}")

    condition = str(data["condition"]).strip()
    if not condition:
        raise DossierError("`condition` must be a non-empty module name")

    generated = data.get("generated") or {}
    if not isinstance(generated, dict):
        raise DossierError("`generated` must be a mapping")
    method = str(generated.get("method", "manual"))
    if method not in ALLOWED_METHODS:
        raise DossierError(
            f"generated.method {method!r} invalid; choices: {list(ALLOWED_METHODS)}"
        )

    snomed = _require_coding(data["codes"].get("snomed"), "codes.snomed", system=SNOMED_SYSTEM)
    icd10 = _parse_icd10(data["codes"].get("icd10"))

    stratify_by, cells, prevalence_citation = _parse_prevalence(data["prevalence"])
    onset_min, onset_max = _parse_onset(data["onset_age"])

    clinical = data.get("clinical") or {}
    if not isinstance(clinical, dict):
        raise DossierError("`clinical` must be a mapping")
    encounters = _parse_encounters(clinical.get("encounters") or [])
    encounter_specs = {e["spec_id"] for e in encounters}
    observations = _parse_observations(clinical.get("observations") or [], encounter_specs)
    medications = _parse_medications(clinical.get("medications") or [], encounter_specs)
    progressions = _parse_progressions(data.get("progressions") or [])

    return Dossier(
        condition=condition,
        version=str(data.get("version", "0.1.0")),
        generated=generated,
        snomed=snomed,
        icd10=icd10,
        prevalence_stratify_by=stratify_by,
        prevalence_cells=cells,
        prevalence_citation=prevalence_citation,
        onset_min=onset_min,
        onset_max=onset_max,
        encounters=encounters,
        observations=observations,
        medications=medications,
        progressions=progressions,
        notes=str(data.get("notes", "")),
        raw=data,
    )


# -- Field parsers -----------------------------------------------------------


def _require_coding(raw: Any, ctx: str, *, system: str | None = None) -> dict[str, str]:
    if not isinstance(raw, dict):
        raise DossierError(f"{ctx}: expected a mapping with code/display")
    for required in ("code", "display"):
        if not raw.get(required):
            raise DossierError(f"{ctx}: missing {required!r}")
    coding = {
        "system": str(raw.get("system") or system or ""),
        "code": str(raw["code"]),
        "display": str(raw["display"]),
    }
    if not coding["system"]:
        raise DossierError(f"{ctx}: missing `system`")
    return coding


def _parse_icd10(raw: Any) -> list[dict[str, str]]:
    if not raw:
        return []
    if not isinstance(raw, list):
        raise DossierError("codes.icd10 must be a list of {code, display}")
    out = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict) or not item.get("code"):
            raise DossierError(f"codes.icd10[{i}] must have a `code`")
        out.append({"code": str(item["code"]), "display": str(item.get("display", ""))})
    return out


def _require_citation(raw: Any, ctx: str) -> dict[str, str]:
    """A citation must carry at least a source. This is the no-uncited-numbers gate."""
    if not isinstance(raw, dict) or not raw.get("source"):
        raise DossierError(
            f"{ctx}: a numeric claim requires a `citation` with at least a `source` "
            f"(this is the dossier's no-uncited-numbers rule)"
        )
    return {str(k): str(v) for k, v in raw.items()}


def _parse_prevalence(raw: Any) -> tuple[str, dict[str, Any], dict[str, str]]:
    if not isinstance(raw, dict):
        raise DossierError("`prevalence` must be a mapping")
    stratify_by = str(raw.get("stratify_by", "age_bracket"))
    if stratify_by not in ALLOWED_STRATIFY:
        raise DossierError(
            f"prevalence.stratify_by {stratify_by!r} invalid; choices: {list(ALLOWED_STRATIFY)}"
        )
    cells = raw.get("cells")
    if not isinstance(cells, dict) or not cells:
        raise DossierError("prevalence.cells must be a non-empty mapping")
    if stratify_by == "sex_and_age":
        bad = set(cells) - set(SEX_KEYS)
        if bad:
            raise DossierError(
                f"prevalence.cells for sex_and_age must use keys {list(SEX_KEYS)}; got extra {sorted(bad)}"
            )
        for sex, brackets in cells.items():
            if not isinstance(brackets, dict) or not brackets:
                raise DossierError(f"prevalence.cells.{sex} must be a non-empty bracket mapping")
    citation = _require_citation(raw.get("citation"), "prevalence.citation")
    return stratify_by, cells, citation


def _parse_onset(raw: Any) -> tuple[int, int]:
    if not isinstance(raw, dict) or "min" not in raw or "max" not in raw:
        raise DossierError("onset_age must be a mapping with `min` and `max`")
    lo, hi = int(raw["min"]), int(raw["max"])
    if lo < 0:
        raise DossierError(f"onset_age.min {lo} must be >= 0")
    if hi < lo:
        raise DossierError(f"onset_age.max {hi} < min {lo}")
    return lo, hi


def _parse_encounters(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        raise DossierError("clinical.encounters must be a list")
    out = []
    for i, e in enumerate(raw):
        ctx = f"clinical.encounters[{i}]"
        if not isinstance(e, dict) or not e.get("spec_id"):
            raise DossierError(f"{ctx}: missing `spec_id`")
        entry: dict[str, Any] = {
            "spec_id": str(e["spec_id"]),
            "class": str(e.get("class", "AMB")),
            "type": _require_coding(e.get("type"), f"{ctx}.type", system=SNOMED_SYSTEM),
        }
        if e.get("reason"):
            entry["reason"] = _require_coding(e["reason"], f"{ctx}.reason", system=SNOMED_SYSTEM)
        out.append(entry)
    return out


def _parse_observations(raw: Any, encounter_specs: set[str]) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        raise DossierError("clinical.observations must be a list")
    out = []
    for i, o in enumerate(raw):
        ctx = f"clinical.observations[{i}]"
        if not isinstance(o, dict) or not o.get("spec_id"):
            raise DossierError(f"{ctx}: missing `spec_id`")
        vr = o.get("value_range")
        if not isinstance(vr, dict) or "low" not in vr or "high" not in vr:
            raise DossierError(f"{ctx}: value_range must be a mapping with low/high")
        category = str(o.get("category", "laboratory"))
        if category not in OBSERVATION_CATEGORIES:
            raise DossierError(
                f"{ctx}: category {category!r} is not generatable; "
                f"choices: {list(OBSERVATION_CATEGORIES)}"
            )
        entry: dict[str, Any] = {
            "spec_id": str(o["spec_id"]),
            "category": category,
            "loinc": _require_coding(o.get("loinc"), f"{ctx}.loinc", system=LOINC_SYSTEM),
            "value_range": {
                "low": float(vr["low"]),
                "high": float(vr["high"]),
                "precision": int(vr.get("precision", 1)),
            },
            "unit": str(o.get("unit", "")),
            "citation": _require_citation(o.get("citation"), f"{ctx}.citation"),
        }
        if o.get("unit_code"):
            entry["unit_code"] = str(o["unit_code"])
        if o.get("link_to"):
            _check_link(str(o["link_to"]), encounter_specs, ctx)
            entry["link_to"] = str(o["link_to"])
        out.append(entry)
    return out


def _parse_medications(raw: Any, encounter_specs: set[str]) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        raise DossierError("clinical.medications must be a list")
    out = []
    for i, m in enumerate(raw):
        ctx = f"clinical.medications[{i}]"
        if not isinstance(m, dict) or not m.get("spec_id"):
            raise DossierError(f"{ctx}: missing `spec_id`")
        if "fraction" not in m:
            raise DossierError(f"{ctx}: missing `fraction` (treated-rate among positives)")
        fraction = float(m["fraction"])
        if not 0.0 <= fraction <= 1.0:
            raise DossierError(f"{ctx}: fraction {fraction} must be in [0, 1]")
        entry: dict[str, Any] = {
            "spec_id": str(m["spec_id"]),
            "medication": _require_coding(m.get("medication"), f"{ctx}.medication"),
            "fraction": fraction,
            "citation": _require_citation(m.get("citation"), f"{ctx}.citation"),
        }
        if m.get("link_to"):
            _check_link(str(m["link_to"]), encounter_specs, ctx)
            entry["link_to"] = str(m["link_to"])
        out.append(entry)
    return out


def _parse_progressions(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        raise DossierError("`progressions` must be a list")
    out = []
    for i, p in enumerate(raw):
        ctx = f"progressions[{i}]"
        if not isinstance(p, dict):
            raise DossierError(f"{ctx}: must be a mapping")
        for required in ("to", "after_years", "probability"):
            if required not in p:
                raise DossierError(f"{ctx}: missing {required!r}")
        probability = float(p["probability"])
        if not 0.0 <= probability <= 1.0:
            raise DossierError(f"{ctx}: probability {probability} must be in [0, 1]")
        out.append(
            {
                "to": str(p["to"]),
                "after_years": int(p["after_years"]),
                "probability": probability,
                "citation": _require_citation(p.get("citation"), f"{ctx}.citation"),
            }
        )
    return out


def _check_link(link_to: str, encounter_specs: set[str], ctx: str) -> None:
    if link_to not in encounter_specs:
        raise DossierError(
            f"{ctx}: link_to={link_to!r} does not match any encounter spec_id "
            f"(available: {sorted(encounter_specs) or '(none)'})"
        )

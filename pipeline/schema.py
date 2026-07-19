"""Canonical entity schema for the construction-intelligence pipeline.

Every source record (HMDA permit, HMDA occupancy, RERA project) is normalized into
one ``Project`` entity. Downstream layers fill in the fields they own:
  - normalize.py  -> identity, promoter, category, dates, source provenance
  - resolve.py    -> merges duplicate source records into one Project
  - geocode.py    -> lat/lng/geo_confidence
  - lifecycle.py  -> stage / stage_confidence / stage_rule
  - score.py      -> lead_score
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class SourceRef:
    """Provenance for one contributing source record."""
    source: str = ""            # e.g. "hmda_autodcr"
    file_no: str = ""
    permit_number: str = ""
    project_type: str = ""      # the source's own type label
    fetched_at: str = ""
    url: str = ""


@dataclass
class Project:
    project_id: str                              # stable id (see normalize.make_project_id)
    name: str = ""                               # display name (promoter/applicant-derived)
    promoter_org: str = ""                       # cleaned organization/promoter name
    is_organization: bool = False                # True if applicant is a company/firm
    architect_se: str = ""

    # location
    district: str = ""
    mandal: str = ""
    village: str = ""
    address_raw: str = ""

    # geo (filled by geocode.py)
    lat: float | None = None
    lng: float | None = None
    geo_confidence: str = "none"                 # exact | village | mandal | district | none

    # classification
    permission_types: list[str] = field(default_factory=list)  # e.g. ["building_permission"]
    category: str = ""                           # construction | layout | occupancy | other
    scale_proxy: float | None = None             # needs detail page; None for now

    # lifecycle dates (ISO yyyy-mm-dd)
    permission_date: str | None = None
    oc_date: str | None = None
    rera_reg_date: str | None = None

    # lifecycle (filled by lifecycle.py)
    stage: str = ""
    stage_confidence: str = ""                    # high | medium | low
    stage_rule: str = ""

    # scoring (filled by score.py)
    lead_score: float | None = None
    score_breakdown: dict[str, float] = field(default_factory=dict)  # transparency

    sources: list[SourceRef] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

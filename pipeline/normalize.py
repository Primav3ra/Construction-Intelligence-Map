"""Normalize raw source records into canonical Project entities.

Input: dicts shaped like scrapers.hmda_search.PermitRecord (from the scraper's
JSONL output). Output: schema.Project objects, one per source record, with:
  - stable project_id
  - promoter/organization classification (privacy-aware: org names are the target
    signal; individuals are flagged, not enriched -- per the brief's privacy note)
  - coarse category + permission-type event
  - lifecycle dates (permission vs occupancy) derived from the source

Cross-source de-duplication/merging is a separate concern (resolve.py). This module
only collapses exact re-scrapes of the same file number.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Iterable

from .schema import Project, SourceRef

# Tokens that mark an applicant as an organization/firm rather than an individual.
_ORG_MARKERS = (
    "M/S", "M/ S", "PVT", "PRIVATE LIMITED", "P LTD", " LTD", "LIMITED", "LLP",
    "BUILDERS", "BUILDER", "INFRA", "INFRACON", "CONSTRUCTION", "DEVELOPER",
    "PROJECTS", "FOUNDATION", "ENTERPRISE", "ESTATE", "REALTY", "REALTORS",
    "HOMES", "HOUSING", "PROCESSORS", "INDUSTRIES", "COMPANY", "CORPORATION",
    "ASSOCIATES", "VENTURES", "TRUST", "SOCIETY", "REP. BY", "REP BY",
    "REPRESENTED BY", "MANAGING PARTNER", "MANAGING DIRECTOR", "DIRECTORS",
)

# Honorific prefixes to strip when deriving a clean display name for individuals.
_HONORIFICS = ("SRI.", "SRI ", "SMT.", "SMT ", "MR.", "MR ", "MRS.", "MRS ",
               "DR.", "DR ", "KUM.", "M/S.", "M/S ")

_CATEGORY_BY_TYPE = {
    "building permission": ("construction", "building_permission"),
    "occupancy": ("occupancy", "occupancy_certificate"),
    "occupancy certificate": ("occupancy", "occupancy_certificate"),
    "layout open plot": ("layout", "layout"),
    "layout with housing": ("layout", "layout"),
    "layout with housing under gated community": ("layout", "layout"),
    "noc": ("other", "noc"),
    "change of land use": ("other", "land_use"),
    "land use": ("other", "land_use"),
}


def is_organization(applicant: str) -> bool:
    up = f" {(applicant or '').upper()} "
    return any(marker in up for marker in _ORG_MARKERS)


def clean_org_name(applicant: str) -> str:
    """Trim the applicant to a stable organization/promoter name.

    For firms, cut off the 'Rep. by ...' / 'Represented By ...' tail so the same
    company scores consistently for promoter-repetition. For individuals, drop
    honorifics.
    """
    name = re.sub(r"\s+", " ", (applicant or "")).strip().rstrip(",")
    if not name:
        return ""
    # cut representative/director tails
    name = re.split(r"\b(?:Rep\.?\s*by|Represented\s+By|Rep\.?\s+by\s+its)\b",
                    name, maxsplit=1, flags=re.IGNORECASE)[0].strip().rstrip(",")
    if not is_organization(applicant):
        up = name.upper()
        for h in _HONORIFICS:
            if up.startswith(h):
                name = name[len(h):].strip()
                break
    return name


def category_and_permission(project_type: str) -> tuple[str, str]:
    key = re.sub(r"\s+", " ", (project_type or "").strip().lower())
    return _CATEGORY_BY_TYPE.get(key, ("other", key.replace(" ", "_") or "unknown"))


def make_project_id(source: str, file_no: str) -> str:
    basis = f"{source}|{(file_no or '').strip().upper()}"
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:16]


def normalize_record(rec: dict) -> Project:
    file_no = (rec.get("file_no") or "").strip()
    source = rec.get("source") or "hmda_autodcr"
    applicant = rec.get("applicant") or ""
    ptype = rec.get("project_type") or rec.get("query_project_type") or ""
    category, permission = category_and_permission(ptype)
    org = is_organization(applicant)
    promoter = clean_org_name(applicant)

    app_date = rec.get("application_date")  # scraper already parses from file_no

    proj = Project(
        project_id=make_project_id(source, file_no),
        name=promoter or applicant.strip(),
        promoter_org=promoter,
        is_organization=org,
        architect_se=(rec.get("architect_se") or "").strip(),
        district=(rec.get("district") or "").strip(),
        village=(rec.get("village") or "").strip(),
        address_raw=", ".join(x for x in [(rec.get("village") or "").strip(),
                                          (rec.get("district") or "").strip()] if x),
        permission_types=[permission],
        category=category,
    )
    # date routing: occupancy vs permission
    if permission == "occupancy_certificate":
        proj.oc_date = app_date
    else:
        proj.permission_date = app_date

    proj.sources.append(SourceRef(
        source=source,
        file_no=file_no,
        permit_number=(rec.get("permit_number") or "").strip(),
        project_type=ptype,
        fetched_at=(rec.get("fetched_at") or "").strip(),
    ))
    return proj


def normalize_batch(records: Iterable[dict]) -> list[Project]:
    """Normalize records, collapsing exact re-scrapes of the same (source, file_no).

    The most recently fetched duplicate wins (keeps the freshest snapshot).
    """
    by_id: dict[str, Project] = {}
    for rec in records:
        proj = normalize_record(rec)
        existing = by_id.get(proj.project_id)
        if existing is None:
            by_id[proj.project_id] = proj
            continue
        # keep the one with the newer fetched_at
        new_ts = proj.sources[0].fetched_at if proj.sources else ""
        old_ts = existing.sources[0].fetched_at if existing.sources else ""
        if new_ts >= old_ts:
            by_id[proj.project_id] = proj
    return list(by_id.values())


def load_jsonl(path: str | Path) -> list[dict]:
    out: list[dict] = []
    with Path(path).open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out

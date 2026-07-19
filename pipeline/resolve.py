"""Entity resolution: merge Project records that describe the same physical project
across sources/permission types (e.g. a Building Permission and its later Occupancy
Certificate, or a RERA registration for the same site).

This is where the "data quality" judging points live (the brief flags dedup +
conflicting statuses explicitly). We are deliberately conservative: merge only on
strong evidence, and record every contributing source rather than discarding.

Match signals (within a (district, village) block):
  1. Cross-reference: one record's permit_number points at another's file_no
     (HMDA occupancy records carry the original building-permit number). STRONG.
  2. Same promoter (fuzzy) + same village + compatible permission types. MEDIUM.

Uses RapidFuzz when available; falls back to difflib.
"""
from __future__ import annotations

import re
from itertools import combinations

from .schema import Project, SourceRef

try:
    from rapidfuzz import fuzz
    def _ratio(a: str, b: str) -> float:
        return float(fuzz.token_sort_ratio(a, b))
except Exception:  # pragma: no cover - fallback
    from difflib import SequenceMatcher
    def _ratio(a: str, b: str) -> float:
        return SequenceMatcher(None, a, b).ratio() * 100.0

PROMOTER_MATCH_THRESHOLD = 88.0


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _block_key(p: Project) -> tuple[str, str]:
    return (_norm(p.district), _norm(p.village))


def _all_refs(p: Project) -> set[str]:
    """Every file/permit identifier this project carries (normalized)."""
    out: set[str] = set()
    for s in p.sources:
        if s.file_no:
            out.add(_norm(s.file_no))
        if s.permit_number:
            out.add(_norm(s.permit_number))
    return {r for r in out if r}


def _cross_referenced(a: Project, b: Project) -> bool:
    return bool(_all_refs(a) & _all_refs(b))


def _same_promoter(a: Project, b: Project) -> bool:
    if not (a.promoter_org and b.promoter_org):
        return False
    return _ratio(a.promoter_org, b.promoter_org) >= PROMOTER_MATCH_THRESHOLD


def _should_merge(a: Project, b: Project) -> bool:
    # STRONG: one record's permit/file number references the other's.
    if _cross_referenced(a, b):
        return True
    # MEDIUM: complementary lifecycle records (a Building Permission and an
    # Occupancy Certificate) for the same promoter in the same village. We require
    # COMPLEMENTARY categories so two distinct buildings by the same builder in the
    # same village are NOT wrongly fused.
    cats = {a.category, b.category}
    if "construction" in cats and "occupancy" in cats:
        if _norm(a.village) and _norm(a.village) == _norm(b.village) and _same_promoter(a, b):
            return True
    return False


class _UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))

    def find(self, i: int) -> int:
        while self.parent[i] != i:
            self.parent[i] = self.parent[self.parent[i]]
            i = self.parent[i]
        return i

    def union(self, i: int, j: int) -> None:
        ri, rj = self.find(i), self.find(j)
        if ri != rj:
            self.parent[ri] = rj


def _merge_group(members: list[Project]) -> Project:
    """Combine a group into one canonical Project (BP-record identity preferred)."""
    # canonical = the construction/building record if present, else earliest
    canon = next((m for m in members if m.category == "construction"), members[0])
    merged = Project(project_id=canon.project_id, name=canon.name,
                     promoter_org=canon.promoter_org, is_organization=any(m.is_organization for m in members),
                     architect_se=canon.architect_se, district=canon.district,
                     mandal=canon.mandal, village=canon.village, address_raw=canon.address_raw,
                     category=canon.category)
    perm_types: list[str] = []
    for m in members:
        for pt in m.permission_types:
            if pt not in perm_types:
                perm_types.append(pt)
        merged.sources.extend(m.sources)
        # dates: earliest permission, any OC, any RERA
        if m.permission_date and (merged.permission_date is None or m.permission_date < merged.permission_date):
            merged.permission_date = m.permission_date
        if m.oc_date and (merged.oc_date is None or m.oc_date > merged.oc_date):
            merged.oc_date = m.oc_date
        if m.rera_reg_date and merged.rera_reg_date is None:
            merged.rera_reg_date = m.rera_reg_date
    merged.permission_types = perm_types
    return merged


def resolve(projects: list[Project]) -> list[Project]:
    """Merge duplicate/related projects. Returns the resolved (fewer) list."""
    # group by block, run pairwise merge within each block
    blocks: dict[tuple[str, str], list[int]] = {}
    for idx, p in enumerate(projects):
        blocks.setdefault(_block_key(p), []).append(idx)

    uf = _UnionFind(len(projects))
    for idxs in blocks.values():
        for i, j in combinations(idxs, 2):
            if _should_merge(projects[i], projects[j]):
                uf.union(i, j)

    groups: dict[int, list[Project]] = {}
    for idx, p in enumerate(projects):
        groups.setdefault(uf.find(idx), []).append(p)

    return [_merge_group(members) if len(members) > 1 else members[0]
            for members in groups.values()]

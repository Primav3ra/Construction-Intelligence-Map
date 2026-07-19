"""Cement lead scoring: rank projects 0-100 for a cement distributor, with a
transparent per-component breakdown (surfaced in the UI's transparency panel).

Business model: cement demand peaks from foundation -> structural completion,
BEFORE the Occupancy Certificate. So the score rewards projects that are approved
(imminent demand) or likely-active (peak structural demand) and heavily discounts
completed ones (demand spent).

score = 100 * sum(weight_i * factor_i), factors in [0,1]:
  stage        - lifecycle stage's cement-demand weight
  recency      - newer permission => sooner/ongoing demand
  scale        - project size proxy (unavailable from the list view -> neutral 0.5;
                 needs the per-permit detail page, tracked as a known limitation)
  proximity    - within the distributor's territory (optional)
  promoter_rep - repeat promoters = warmer, relationship-driven leads
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import re

from .schema import Project
from .lifecycle import _months_between


@dataclass(frozen=True)
class Weights:
    stage: float = 0.35
    recency: float = 0.20
    scale: float = 0.15
    proximity: float = 0.15
    promoter_rep: float = 0.15


_STAGE_WEIGHT = {
    "likely_active": 1.00,   # structural phase -> peak cement demand
    "approved": 0.85,        # imminent demand
    "unknown": 0.30,
    "stale_unknown": 0.25,
    "completed": 0.05,       # demand largely spent
}

_NEUTRAL_SCALE = 0.5         # until per-permit built-up area is scraped


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _recency_factor(project: Project, as_of: date) -> float:
    age = _months_between(project.permission_date, as_of)
    if age is None:
        return 0.4
    if age < 0:
        return 1.0
    return max(0.0, 1.0 - age / 36.0)


def _proximity_factor(project: Project, territory: dict | None) -> float:
    """territory = {"districts": [...], "villages": [...]} (names). None => no filter."""
    if not territory:
        return 1.0
    villages = {_norm(v) for v in territory.get("villages", [])}
    districts = {_norm(d) for d in territory.get("districts", [])}
    if villages and _norm(project.village) in villages:
        return 1.0
    if districts and _norm(project.district) in districts:
        return 0.6
    return 0.15


def _promoter_counts(projects: list[Project]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for p in projects:
        key = _norm(p.promoter_org)
        if key:
            counts[key] = counts.get(key, 0) + 1
    return counts


def _promoter_rep_factor(project: Project, counts: dict[str, int]) -> float:
    n = counts.get(_norm(project.promoter_org), 1)
    return min(1.0, (n - 1) / 4.0)   # 1 project -> 0.0, 5+ -> 1.0


def score_batch(projects: list[Project], *, as_of: date,
                territory: dict | None = None, weights: Weights = Weights()) -> list[Project]:
    """Compute lead_score + score_breakdown for each project (mutates in place)."""
    counts = _promoter_counts(projects)
    for p in projects:
        factors = {
            "stage": _STAGE_WEIGHT.get(p.stage, 0.3),
            "recency": _recency_factor(p, as_of),
            "scale": _NEUTRAL_SCALE if p.scale_proxy is None else min(1.0, p.scale_proxy),
            "proximity": _proximity_factor(p, territory),
            "promoter_rep": _promoter_rep_factor(p, counts),
        }
        w = weights
        total = (w.stage * factors["stage"] + w.recency * factors["recency"]
                 + w.scale * factors["scale"] + w.proximity * factors["proximity"]
                 + w.promoter_rep * factors["promoter_rep"])
        p.lead_score = round(100.0 * total, 1)
        p.score_breakdown = {k: round(v, 3) for k, v in factors.items()}
    return projects


def rank(projects: list[Project]) -> list[Project]:
    return sorted(projects, key=lambda p: (p.lead_score or 0.0), reverse=True)

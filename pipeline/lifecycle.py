"""Lifecycle inference: map a resolved Project's records to a construction stage,
with an explicit confidence level and the rule that produced it.

The brief is emphatic that a permit is NOT proof of physical construction, so every
stage is an *inference* carried with its rule + confidence, never asserted as fact.

Stages (cement-demand oriented):
  R4 completed      -> Occupancy Certificate present. Demand largely SPENT.        [high]
  R1 approved       -> permission recent, no OC. Pre-construction; demand IMMINENT. [high approved / low started]
  R3 likely_active  -> permission aged into the typical build window, no OC.
                       Structural phase = PEAK cement demand.                       [medium]
  R5 stale_unknown  -> permission very old, still no OC (stalled/lapsed/unrecorded).[low]

Windows are configurable and expressed in months from the permission date.
Pure functions: the reference date is passed in (`as_of`) for testability.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .schema import Project


@dataclass(frozen=True)
class LifecycleConfig:
    approved_max_months: int = 6      # <=6mo since permission, no OC -> pre-construction
    active_max_months: int = 36       # 6-36mo, no OC -> likely active (structural)
    # >active_max_months, no OC -> stale/unknown


def _months_between(d0: str | None, as_of: date) -> int | None:
    if not d0:
        return None
    try:
        y, m, dd = (int(x) for x in d0.split("-"))
        start = date(y, m, dd)
    except Exception:  # noqa: BLE001
        return None
    return (as_of.year - start.year) * 12 + (as_of.month - start.month)


def classify(project: Project, *, as_of: date, config: LifecycleConfig = LifecycleConfig()
             ) -> tuple[str, str, str]:
    """Return (stage, confidence, rule_id). Does not mutate the project."""
    if project.oc_date:
        return ("completed", "high", "R4:oc_present")

    age = _months_between(project.permission_date, as_of)
    if age is None:
        # we have a record but no usable permission date
        return ("unknown", "low", "R0:no_date")
    if age < 0:
        # permission dated in the future relative to as_of (data glitch)
        return ("approved", "low", "R1:future_date")
    if age <= config.approved_max_months:
        return ("approved", "high", "R1:recent_permission_no_oc")
    if age <= config.active_max_months:
        return ("likely_active", "medium", "R3:in_build_window_no_oc")
    return ("stale_unknown", "low", "R5:old_permission_no_oc")


def apply_lifecycle(projects: list[Project], *, as_of: date,
                    config: LifecycleConfig = LifecycleConfig()) -> list[Project]:
    for p in projects:
        stage, conf, rule = classify(p, as_of=as_of, config=config)
        p.stage, p.stage_confidence, p.stage_rule = stage, conf, rule
    return projects

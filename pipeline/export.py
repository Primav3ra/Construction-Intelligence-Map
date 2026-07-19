"""Export resolved+scored projects to the static artifacts the web app consumes:
  - projects.geojson : map layer (one Point feature per located project)
  - leads.json       : ranked cement lead list
  - meta.json        : refresh timestamp, coverage, counts, confidence summary

These are committed to data/ and served statically (no backend).
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path

from .schema import Project
from .score import rank

# Single canonical location for published artifacts: the web app's public dir
# (served directly by the static site; no duplicate copy elsewhere).
DATA_DIR = Path(__file__).resolve().parents[1] / "web" / "public" / "data"
REFRESH_CADENCE = "weekly"


def _properties(p: Project) -> dict:
    return {
        "project_id": p.project_id,
        "name": p.name,
        "promoter_org": p.promoter_org,
        "is_organization": p.is_organization,
        "district": p.district,
        "village": p.village,
        "category": p.category,
        "permission_types": p.permission_types,
        "permission_date": p.permission_date,
        "oc_date": p.oc_date,
        "stage": p.stage,
        "stage_confidence": p.stage_confidence,
        "stage_rule": p.stage_rule,
        "geo_confidence": p.geo_confidence,
        "lead_score": p.lead_score,
        "score_breakdown": p.score_breakdown,
        "sources": [
            {"source": s.source, "file_no": s.file_no, "permit_number": s.permit_number,
             "project_type": s.project_type, "fetched_at": s.fetched_at}
            for s in p.sources
        ],
    }


def projects_geojson(projects: list[Project]) -> dict:
    features = []
    for p in projects:
        if p.lat is None or p.lng is None:
            continue  # no location -> not mappable (still counted in meta)
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [p.lng, p.lat]},
            "properties": _properties(p),
        })
    return {"type": "FeatureCollection", "features": features}


def leads_json(projects: list[Project], *, top_n: int | None = None) -> list[dict]:
    ranked = rank(projects)
    if top_n:
        ranked = ranked[:top_n]
    return [
        {
            "project_id": p.project_id,
            "lead_score": p.lead_score,
            "name": p.name,
            "promoter_org": p.promoter_org,
            "is_organization": p.is_organization,
            "district": p.district,
            "village": p.village,
            "stage": p.stage,
            "stage_confidence": p.stage_confidence,
            "permission_date": p.permission_date,
            "geo_confidence": p.geo_confidence,
            "score_breakdown": p.score_breakdown,
            "file_no": p.sources[0].file_no if p.sources else "",
        }
        for p in ranked
    ]


def meta_json(projects: list[Project], *, generated_at: str | None = None,
              sources: list[str] | None = None) -> dict:
    located = sum(1 for p in projects if p.lat is not None)
    return {
        "generated_at": generated_at or datetime.now().isoformat(timespec="seconds"),
        "refresh_cadence": REFRESH_CADENCE,
        "record_count": len(projects),
        "mapped_count": located,
        "geo_coverage_pct": round(100.0 * located / len(projects), 1) if projects else 0.0,
        "by_stage": dict(Counter(p.stage for p in projects)),
        "by_district": dict(Counter(p.district for p in projects)),
        "by_geo_confidence": dict(Counter(p.geo_confidence for p in projects)),
        "sources": sources or sorted({s.source for p in projects for s in p.sources}),
        "disclaimer": ("Stages are INFERRED from administrative records (permits/OCs), "
                       "not confirmations of physical construction. Each carries a rule "
                       "and confidence. Data reflects the last refresh; see generated_at."),
    }


def write_artifacts(projects: list[Project], *, out_dir: Path = DATA_DIR,
                    generated_at: str | None = None, top_n: int | None = None,
                    sources: list[str] | None = None) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "projects": out_dir / "projects.geojson",
        "leads": out_dir / "leads.json",
        "meta": out_dir / "meta.json",
    }
    paths["projects"].write_text(json.dumps(projects_geojson(projects), ensure_ascii=False, indent=1), encoding="utf-8")
    paths["leads"].write_text(json.dumps(leads_json(projects, top_n=top_n), ensure_ascii=False, indent=1), encoding="utf-8")
    paths["meta"].write_text(json.dumps(meta_json(projects, generated_at=generated_at, sources=sources), ensure_ascii=False, indent=1), encoding="utf-8")
    return paths

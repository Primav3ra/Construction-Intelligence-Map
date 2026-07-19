"""Pipeline orchestrator: raw source JSONL -> canonical artifacts in data/.

    raw records --normalize--> resolve --> geocode --> lifecycle --> score --> export

Usage:
    python -m pipeline.run --input pipeline/raw_cache/hmda_records.jsonl \
        --out data --as-of 2026-07-19 --top 100
"""
from __future__ import annotations

import argparse
from datetime import date, datetime
from pathlib import Path

from .normalize import normalize_batch, load_jsonl
from .resolve import resolve
from .geocode import geocode_batch, CACHE_PATH
from .lifecycle import apply_lifecycle, LifecycleConfig
from .score import score_batch, Weights
from .export import write_artifacts
from .schema import Project


def run_pipeline(input_path: str | Path, *, out_dir: Path, as_of: date,
                 territory: dict | None = None, allow_network: bool = True,
                 top_n: int | None = None, cache_path: Path = CACHE_PATH,
                 generated_at: str | None = None) -> tuple[list[Project], dict]:
    raw = load_jsonl(input_path)
    projects = normalize_batch(raw)
    projects = resolve(projects)
    geocode_batch(projects, cache_path=cache_path, allow_network=allow_network)
    apply_lifecycle(projects, as_of=as_of, config=LifecycleConfig())
    score_batch(projects, as_of=as_of, territory=territory, weights=Weights())
    paths = write_artifacts(projects, out_dir=out_dir, top_n=top_n,
                            generated_at=generated_at)
    return projects, paths


def _cli() -> int:
    ap = argparse.ArgumentParser(description="Construction-intelligence pipeline")
    ap.add_argument("--input", required=True, help="raw records JSONL (scraper output)")
    ap.add_argument("--out", default="web/public/data", help="artifact output dir")
    ap.add_argument("--as-of", default=None, help="reference date yyyy-mm-dd (default: today)")
    ap.add_argument("--offline", action="store_true", help="skip Nominatim; district-centroid geocode only")
    ap.add_argument("--top", type=int, default=None, help="cap lead list length")
    args = ap.parse_args()

    as_of = date.fromisoformat(args.as_of) if args.as_of else date.today()
    projects, paths = run_pipeline(
        args.input, out_dir=Path(args.out), as_of=as_of,
        allow_network=not args.offline, top_n=args.top,
        generated_at=datetime.now().isoformat(timespec="seconds"),
    )
    print(f"pipeline: {len(projects)} projects -> "
          f"{paths['projects'].name}, {paths['leads'].name}, {paths['meta'].name} in {args.out}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())

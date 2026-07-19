"""Sweep the HMDA AutoDCR portal across districts x permission-types x month windows
and write combined raw records to a JSONL the pipeline consumes.

Monthly windows keep each result set small (fewer virtual-scroll appends) and make
partial failures cheap to isolate. One browser session is reused across queries.

Usage:
    python -m pipeline.scrape_hmda --districts "Medchal-Malkajgiri,Ranga Reddy" \
        --months 12 --out pipeline/raw_cache/hmda_records.jsonl

Note: verified per-query against the identical AutoDCR engine (GHMC). Run once
manually against live HMDA to confirm coverage before relying on the cron.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import date
from pathlib import Path

from playwright.sync_api import sync_playwright

from .scrapers.hmda_search import search, months, UA, DISTRICTS, PROJECT_TYPES

DEFAULT_DISTRICTS = ["Medchal-Malkajgiri", "Ranga Reddy", "Sanga Reddy"]
DEFAULT_TYPES = ["Building Permission", "Occupancy"]
DEFAULT_OUT = Path(__file__).resolve().parent / "raw_cache" / "hmda_records.jsonl"


def _month_windows(lookback_months: int, as_of: date) -> list[tuple[str, str]]:
    # start = first day of the month `lookback_months` ago
    y, m = as_of.year, as_of.month
    total = y * 12 + (m - 1) - lookback_months
    sy, sm = divmod(total, 12)
    start = f"01/{sm + 1:02d}/{sy:04d}"
    end = as_of.strftime("%d/%m/%Y")
    return list(months(start, end))


def sweep(*, districts: list[str], types: list[str], lookback_months: int,
          as_of: date, out_path: Path, max_rows: int = 3000,
          headful: bool = False) -> int:
    windows = _month_windows(lookback_months, as_of)
    seen: set[str] = set()
    records: list[dict] = []
    print(f"sweep: {len(districts)} districts x {len(types)} types x {len(windows)} months "
          f"= {len(districts) * len(types) * len(windows)} queries")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headful)
        page = browser.new_page(user_agent=UA)
        page.set_default_timeout(60000)
        page.on("dialog", lambda d: d.accept())
        for district in districts:
            if district not in DISTRICTS:
                print(f"  ! skipping unknown district {district!r}")
                continue
            for ptype in types:
                if ptype not in PROJECT_TYPES:
                    print(f"  ! skipping unknown type {ptype!r}")
                    continue
                for fd, td in windows:
                    try:
                        recs = search(page, project_type=ptype, district=district,
                                      from_date=fd, to_date=td, max_rows=max_rows)
                    except Exception as e:  # noqa: BLE001 - isolate per-query failures
                        print(f"  ! {district}/{ptype}/{fd}..{td} FAILED: {type(e).__name__}: {e}")
                        continue
                    for r in recs:
                        d = asdict(r)
                        key = f"{d['source']}|{d['file_no']}"
                        if d["file_no"] and key not in seen:
                            seen.add(key)
                            records.append(d)
        browser.close()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        for d in records:
            fh.write(json.dumps(d, ensure_ascii=False) + "\n")
    print(f"sweep done: {len(records)} unique records -> {out_path}")
    return len(records)


def _cli() -> int:
    ap = argparse.ArgumentParser(description="HMDA multi-district sweep")
    ap.add_argument("--districts", default=",".join(DEFAULT_DISTRICTS))
    ap.add_argument("--types", default=",".join(DEFAULT_TYPES))
    ap.add_argument("--months", type=int, default=12, help="lookback window in months")
    ap.add_argument("--as-of", default=None, help="reference date yyyy-mm-dd (default today)")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--headful", action="store_true")
    args = ap.parse_args()
    as_of = date.fromisoformat(args.as_of) if args.as_of else date.today()
    n = sweep(districts=[d.strip() for d in args.districts.split(",") if d.strip()],
              types=[t.strip() for t in args.types.split(",") if t.strip()],
              lookback_months=args.months, as_of=as_of, out_path=Path(args.out),
              headful=args.headful)
    return 0 if n else 2


if __name__ == "__main__":
    raise SystemExit(_cli())

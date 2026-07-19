"""
HMDA DPMS AutoDCR public-search scraper (verified backbone source).

Drives the live portal with a headless browser (Playwright) because the site is a
Telerik/RadAjax ASP.NET app that returns HTTP 500 to hand-built form posts.
Recipe verified in research/spike/ (see docs/SPIKE_FINDINGS.md):

  1. goto(url, wait_until="networkidle")
  2. Selects are hidden native <select> under a Telerik overlay -> set via JS
     (el.value=v; dispatchEvent('change')) which fires the RadAjax cascade.
  3. Date boxes are readonly (calendar-only) -> remove readonly and set the
     #txt* boxes AND the #hid* mirrors via JS. Date filter works on HMDA.
  4. Search = click('#btnSave') -> clkSearch() -> RadAjax binds #PublicSearchGrid.
  5. Read rows; paginate via the RadGrid pager; "Total Proposal(s) : N" = count.

Per-record fields include the application DATE embedded in the file number
(trailing DDMMYYYY) and the promoter/org name in the applicant field.

Usage:
    python -m pipeline.scrapers.hmda_search \
        --district "Medchal-Malkajgiri" --type "Building Permission" \
        --from 01/01/2024 --to 31/12/2024

This module only *fetches and parses*; normalization/storage live downstream.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass, asdict, field
from datetime import date, datetime
from pathlib import Path
from typing import Iterable

from playwright.sync_api import sync_playwright, Page, TimeoutError as PWTimeout

HMDA_URL = "https://dpms.hmda.gov.in/AutoDCR.Common2/CitizenSearch/publicsearch.aspx"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

# Verified option values (research/spike/probe14_recency_hmda.py).
# NOTE: several districts return 0 rows for recent windows -- coverage varies and
# is confirmed at runtime, not assumed. Medchal-Malkajgiri is the richest.
DISTRICTS: dict[str, str] = {
    "Hyderabad": "946",
    "Mahaboobnagar": "20",
    "Medak District": "7",
    "Medchal-Malkajgiri": "1290",
    "Nalgonda": "19",
    "Ranga Reddy": "12",
    "Sanga Reddy": "1291",
    "Siddipet": "1292",
    "Yadadri": "1293",
}
PROJECT_TYPES: dict[str, str] = {
    "Building Permission": "14",
    "Layout with Housing Under Gated Community": "30",
    "NOC": "33",
    "Layout Open Plot": "29",
    "Change of Land Use": "43",
    "Layout with Housing": "44",
    "Occupancy": "40",
    "Land Use": "45",
}

RAW_CACHE = Path(__file__).resolve().parents[1] / "raw_cache" / "hmda"

# ---------------------------------------------------------------- data model

@dataclass
class PermitRecord:
    file_no: str = ""
    case_type: str = ""
    project_type: str = ""
    applicant: str = ""
    architect_se: str = ""
    village: str = ""
    permit_number: str = ""
    pid: str = ""            # internal proposal id (last numeric cells)
    mid: str = ""
    application_date: str | None = None   # ISO yyyy-mm-dd, parsed from file_no
    # provenance (filled by caller)
    district: str = ""
    source: str = "hmda_autodcr"
    query_project_type: str = ""
    fetched_at: str = ""

    def key(self) -> str:
        return self.file_no or f"{self.permit_number}|{self.applicant}|{self.village}"


# ---------------------------------------------------------------- helpers

def _squash(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()


def parse_file_no_date(file_no: str) -> str | None:
    """HMDA file numbers end in DDMMYYYY, e.g. '062254/GHT/R1/U6/HMDA/02012024'."""
    m = re.search(r"(\d{2})(\d{2})(\d{4})\s*$", (file_no or "").strip())
    if not m:
        return None
    dd, mm, yyyy = m.groups()
    try:
        return date(int(yyyy), int(mm), int(dd)).isoformat()
    except ValueError:
        return None


def _goto_with_retries(page: Page, url: str, retries: int = 3, backoff: float = 5.0) -> None:
    last: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            page.goto(url, wait_until="networkidle", timeout=45000)
            return
        except (PWTimeout, Exception) as e:  # noqa: BLE001 - gov portals are flaky
            last = e
            if attempt < retries:
                wait = backoff * attempt
                print(f"  goto attempt {attempt} failed ({type(e).__name__}); retrying in {wait:.0f}s",
                      file=sys.stderr)
                time.sleep(wait)
    raise RuntimeError(f"could not load {url} after {retries} attempts: {last}")


def _set_select(page: Page, sid: str, value: str) -> None:
    """Hidden native <select> under a Telerik overlay -> set + fire change (cascade)."""
    page.eval_on_selector(
        sid,
        "(el, v) => { el.value = v; el.dispatchEvent(new Event('change', {bubbles: true})); }",
        value,
    )


def _settle(page: Page, ms: int = 2200) -> None:
    page.wait_for_timeout(ms)
    try:
        page.wait_for_load_state("networkidle", timeout=30000)
    except PWTimeout:
        pass


def _set_dates(page: Page, from_date: str, to_date: str) -> None:
    """Date boxes are readonly (calendar only); set text + hidden mirrors via JS."""
    page.evaluate(
        """(v) => {
            function s(id, val) {
                var e = document.getElementById(id);
                if (e) { e.removeAttribute('readonly'); e.value = val;
                         e.dispatchEvent(new Event('change', {bubbles: true})); }
            }
            s('txtFromDate', v.f); s('txtToDate', v.t);
            var a = document.getElementById('hidDtFrom'); if (a) a.value = v.f;
            var b = document.getElementById('hidDtTo');   if (b) b.value = v.t;
        }""",
        {"f": from_date, "t": to_date},
    )


# Extract immediate-child <td> texts for each data row. The grid is a nested
# custom "GridLib" (class GLDataRow), so we read DIRECT children only -- the outer
# container GLDataRow yields its 1-2 wrapper cells (no file-no -> filtered out),
# while true data rows yield their full cell set.
_ROW_JS = r"""
() => {
  const out = [];
  document.querySelectorAll('#PublicSearchGrid tr.GLDataRow').forEach(tr => {
    const cells = Array.from(tr.children)
      .filter(n => n.tagName === 'TD')
      .map(td => (td.innerText || '').replace(/ /g, ' ').replace(/\s+/g, ' ').trim());
    out.push(cells);
  });
  return out;
}
"""

# A file/permit number: has a slash + digits, not a bare integer, reasonably long.
_FILE_NO_RE = re.compile(r"^\S*\d\S*/\S+")


def _looks_like_file_no(cell: str) -> bool:
    return ("/" in cell and any(ch.isdigit() for ch in cell)
            and not cell.isdigit() and len(cell) >= 6)


def _total_proposals(page: Page) -> int | None:
    try:
        body = page.inner_text("#PublicSearchGrid")
    except Exception:  # noqa: BLE001
        return None
    m = re.search(r"Total Proposal\(s\)\s*:\s*(\d+)", body)
    return int(m.group(1)) if m else None


def _parse_page_rows(page: Page) -> list[PermitRecord]:
    """Parse the current grid page. Anchors each row on its file number and reads
    the leading columns by offset (stable order across GHMC/HMDA):
        file_no, case_type, project_type, applicant, architect_se, village, permit_number.
    PID/MID are the large integer cells near the end. Trailing link/flag columns
    differ between instances, so we never index from the end for the named fields.
    """
    out: list[PermitRecord] = []
    for cells in page.evaluate(_ROW_JS):
        # locate the file-number anchor
        file_idx = next((i for i, c in enumerate(cells) if _looks_like_file_no(c)), None)
        if file_idx is None or len(cells) - file_idx < 3:
            continue  # container/nav row, not a data row
        def at(off: int) -> str:
            j = file_idx + off
            return cells[j] if 0 <= j < len(cells) else ""
        rec = PermitRecord(
            file_no=at(0), case_type=at(1), project_type=at(2), applicant=at(3),
            architect_se=at(4), village=at(5), permit_number=at(6),
        )
        # PID/MID: the substantial integer cells (skip trailing single-digit flags)
        big_ints = [c for c in cells if c.isdigit() and len(c) >= 3]
        if len(big_ints) >= 1:
            rec.pid = big_ints[0]
        if len(big_ints) >= 2:
            rec.mid = big_ints[1]
        # permit_number sometimes lands on a spacer; if blank, take the next file-no-like cell after applicant
        if not _looks_like_file_no(rec.permit_number):
            later = [c for c in cells[file_idx + 1:] if _looks_like_file_no(c)]
            rec.permit_number = later[0] if later else rec.permit_number
        rec.application_date = parse_file_no_date(rec.file_no)
        out.append(rec)
    return out


def _data_row_count(page: Page) -> int:
    """Count rendered data rows (rows whose immediate cells contain a file number)."""
    try:
        rows = page.evaluate(_ROW_JS)
    except Exception:  # noqa: BLE001
        return 0
    return sum(1 for cells in rows if any(_looks_like_file_no(c) for c in cells))


def _advance_grid(page: Page) -> bool:
    """The result grid (SigmaGrid, ``Grids[0]``) holds ALL matching rows client-side
    and renders 16 at a time; GoToNextPage() *appends* the next chunk to the DOM.
    Returns True if the rendered row count grew.
    """
    before = _data_row_count(page)
    try:
        page.evaluate(
            "() => { if (typeof Grids !== 'undefined' && Grids[0] && Grids[0].GoToNextPage) "
            "Grids[0].GoToNextPage(); }"
        )
    except Exception:  # noqa: BLE001
        return False
    page.wait_for_timeout(400)  # client-side render only; no network
    return _data_row_count(page) > before


# ---------------------------------------------------------------- public API

def search(
    page: Page,
    *,
    project_type: str,
    district: str,
    from_date: str | None = None,
    to_date: str | None = None,
    max_rows: int = 3000,
    cache_dir: Path | None = RAW_CACHE,
    url: str = HMDA_URL,
    districts: dict[str, str] = DISTRICTS,
    project_types: dict[str, str] = PROJECT_TYPES,
) -> list[PermitRecord]:
    """Run one AutoDCR search and return de-duplicated PermitRecords (all pages).

    Defaults target HMDA. The GHMC AutoDCR instance shares the identical Telerik
    engine/DOM, so passing its ``url`` + code maps drives the same code path
    (used to validate parsing/pagination when HMDA is unreachable).
    """
    if project_type not in project_types:
        raise ValueError(f"unknown project_type {project_type!r}; known: {list(project_types)}")
    if district not in districts:
        raise ValueError(f"unknown district {district!r}; known: {list(districts)}")

    _goto_with_retries(page, url)
    page.wait_for_timeout(1000)
    _set_select(page, "#cboProjecttype", project_types[project_type])
    _settle(page)
    _set_select(page, "#cboDistric", districts[district])
    _settle(page)
    if from_date and to_date:
        _set_dates(page, from_date, to_date)

    page.click("#btnSave")
    _settle(page, 5000)

    fetched_at = datetime.now().isoformat(timespec="seconds")
    total = _total_proposals(page)

    # Load all matching rows into the DOM (SigmaGrid appends 16 per GoToNextPage).
    loaded = _data_row_count(page)
    stalls = 0
    while loaded < max_rows:
        if not _advance_grid(page):
            stalls += 1
            if stalls >= 2:
                break
        else:
            stalls = 0
        loaded = _data_row_count(page)
    capped = loaded >= max_rows

    if cache_dir:
        _cache_raw(page, cache_dir, project_type, district, from_date, to_date)

    seen: set[str] = set()
    records: list[PermitRecord] = []
    for rec in _parse_page_rows(page):
        k = rec.key()
        if k and k not in seen:
            seen.add(k)
            rec.district = district
            rec.query_project_type = project_type
            rec.fetched_at = fetched_at
            records.append(rec)

    note = f" (CAPPED at max_rows={max_rows}!)" if capped else ""
    print(f"  [{district} / {project_type} / {from_date}..{to_date}] "
          f"total_reported={total} parsed={len(records)}{note}")
    return records


def _cache_raw(page: Page, cache_dir: Path, ptype: str, district: str,
               fd: str | None, td: str | None) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    tag = f"{district}_{ptype}_{(fd or 'na').replace('/','')}_{(td or 'na').replace('/','')}"
    tag = re.sub(r"[^A-Za-z0-9_.-]", "-", tag)
    grid = page.query_selector("#PublicSearchGrid")
    html = grid.inner_html() if grid else page.content()
    (cache_dir / f"{tag}.html").write_text(html, encoding="utf-8")


def months(start: str, end: str) -> Iterable[tuple[str, str]]:
    """Yield (from,to) dd/MM/yyyy month windows between two dd/MM/yyyy dates."""
    s = datetime.strptime(start, "%d/%m/%Y").date()
    e = datetime.strptime(end, "%d/%m/%Y").date()
    y, m = s.year, s.month
    while (y, m) <= (e.year, e.month):
        first = date(y, m, 1)
        nm_y, nm_m = (y + 1, 1) if m == 12 else (y, m + 1)
        last = date(nm_y, nm_m, 1).toordinal() - 1
        last = date.fromordinal(last)
        yield first.strftime("%d/%m/%Y"), last.strftime("%d/%m/%Y")
        y, m = nm_y, nm_m


# ---------------------------------------------------------------- CLI

def _run_cli() -> int:
    ap = argparse.ArgumentParser(description="HMDA AutoDCR public-search scraper")
    ap.add_argument("--district", default="Medchal-Malkajgiri", choices=list(DISTRICTS))
    ap.add_argument("--type", dest="ptype", default="Building Permission", choices=list(PROJECT_TYPES))
    ap.add_argument("--from", dest="from_date", default=None, help="dd/MM/yyyy")
    ap.add_argument("--to", dest="to_date", default=None, help="dd/MM/yyyy")
    ap.add_argument("--max-rows", type=int, default=3000, help="safety cap per query")
    ap.add_argument("--headful", action="store_true", help="show the browser")
    ap.add_argument("--out", default=None, help="write parsed records to this JSONL")
    args = ap.parse_args()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.headful)
        page = browser.new_page(user_agent=UA)
        page.set_default_timeout(60000)
        page.on("dialog", lambda d: d.accept())
        try:
            recs = search(page, project_type=args.ptype, district=args.district,
                          from_date=args.from_date, to_date=args.to_date,
                          max_rows=args.max_rows)
        finally:
            browser.close()

    for r in recs[:10]:
        print(json.dumps({k: v for k, v in asdict(r).items()
                          if k in ("file_no", "application_date", "project_type",
                                   "applicant", "village", "permit_number")},
                         ensure_ascii=False))
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", encoding="utf-8") as fh:
            for r in recs:
                fh.write(json.dumps(asdict(r), ensure_ascii=False) + "\n")
        print(f"wrote {len(recs)} records -> {out}")
    return 0 if recs else 2


if __name__ == "__main__":
    raise SystemExit(_run_cli())

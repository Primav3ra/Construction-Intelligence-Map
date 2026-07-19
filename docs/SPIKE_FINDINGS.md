# Data-Sourcing Verification Spike — Findings

**Date:** 2026-07-17 · **Method:** drove the live government portals with real HTTP probes + headless Playwright. The verified recipe below is codified in [`pipeline/scrapers/hmda_search.py`](../pipeline/scrapers/hmda_search.py).

## Question

Can we pull **broad, area-based, current** construction-permission records for Hyderabad from public portals — and how?

## Verdict: GO (via HMDA + Playwright)

| Source | Access | Data currency | Method | Verdict |
|---|---|---|---|---|
| **HMDA DPMS AutoDCR** | No CAPTCHA. Broad discovery by project type + district (+ mandal/village + date). | **Current — 2024+ confirmed** (Medchal-Malkajgiri BP 2024–25 → 23 real Jan–May 2024 permits, paginated). | Playwright (headless browser) | ✅ **Backbone** |
| GHMC DPMS AutoDCR | No CAPTCHA, works. | **Frozen ~2017–2020** (2024–25 filter → 0 rows). GHMC-core moved to bPASS→BuildNow. | — | ⚠️ Historical only |
| eodb.ghmc OC search | No CAPTCHA. | **HTTP 500 on every query, even via real browser** — broken server-side. | — | ❌ Dropped |
| TG-RERA (`rerait...`) | Public + permissive terms, but **mandatory image CAPTCHA** + incomplete TLS chain. | Current. | Human-in-loop Playwright | 🔒 Semi-manual enrichment |

## Why raw HTTP fails (and Playwright is required)

The portals are ASP.NET **Telerik/RadAjax** apps. Hand-built form posts hit `500 | Object reference not set...` (AutoDCR) or generic 500s (eodb) because dropdowns are populated client-side and search binds a RadGrid via AJAX delta postback. A real browser sidesteps all of it.

## Verified HMDA ingestion recipe

Endpoint: `https://dpms.hmda.gov.in/AutoDCR.Common2/CitizenSearch/publicsearch.aspx`

1. `goto(url, wait_until="networkidle")`.
2. Selects are **hidden native `<select>`** (Telerik overlay) → set via JS:
   `el.value=v; el.dispatchEvent(new Event('change',{bubbles:true}))` (fires the RadAjax cascade).
   - `#cboProjecttype`: `14`=Building Permission, `40`=Occupancy, `29`/`30`/`44`=Layouts, `33`=NOC.
   - `#cboDistric`, `#cboMandal`, `#CboVillage` (cascading).
3. Date boxes are **readonly** (calendar-only) → remove `readonly`, set `#txtFromDate`/`#txtToDate` **and** `#hidDtFrom`/`#hidDtTo` via JS. (Date filter confirmed working on HMDA; NOT on frozen GHMC.)
4. Search: `click('#btnSave')` (→ `clkSearch()` → RadAjax). Read `#PublicSearchGrid` rows; paginate via RadGrid pager; `Total Proposal(s) : N` = count.

### Fields returned per record

`File No.` (⚑ **application date embedded as trailing DDMMYYYY**, e.g. `062254/GHT/R1/U6/HMDA/02012024`) · `Case Type` · `Project Type` · `Name of Applicant` (⚑ **promoter/org names**, e.g. "M/s KAKATIYA INFRA PROJECTS") · `Architect/SE Name` · `Village` · `Permit Number` · `PID`/`MID` · detail links (View Proceeding / Drawing / Certificate).

So application **dates** and **promoter identities** come for free — no extra scraping.

## Reused assets (verified loadable)

- **datameet/Municipal_Spatial_Data** Hyderabad GeoJSON: 145 wards / 5 zones / boundary (2017–18 vintage). **No circle polygons.**
- **gggodhwani/telangana_boundaries**: mandal/village polygons (for HMDA geography).
- **pgeocode**: resolves Hyderabad pincodes → locality + coords (coarse anchor).

## Coverage caveats

- HMDA coverage varies by district: **Medchal-Malkajgiri rich**; RangaReddy 2025 returned 0. Verify each district on day 1.
- Territory maps at **zone / district / village** level (no circle polygons; suits HMDA geography anyway).

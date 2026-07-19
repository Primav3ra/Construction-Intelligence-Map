# Hyderabad Construction Intelligence Map — Build Plan (evidence-based, post-spike)

> In-repo mirror of the working plan. Companion: [SPIKE_FINDINGS.md](SPIKE_FINDINGS.md).

## Context

Turn scattered public building-permission records into an actionable, map-based "construction intelligence layer" for **small cement distributors** in Hyderabad (full brief in the hackathon PDF). The map is table stakes; the win is the **translation layer**: permit records → confidence-scored construction lifecycle → a **ranked weekly lead list scoped to a distributor's territory**.

**Core business insight:** cement is consumed most heavily from foundation → structural completion, *before* the Occupancy Certificate. So the top lead = a project with a **recent Building Permission and no OC yet**, weighted by scale and located in the distributor's area. Occupancy = demand largely spent.

**Timeline/resources:** 1–2 weeks, small team. Free-tier only. Batch → static-artifact architecture (weekly refresh, static site) — zero server to fail during judging; the weekly cadence is our honest refresh story.

## Verified reality (drove the live portals in the spike — supersedes earlier recon)

| Source | Finding (first-hand) | Role |
|---|---|---|
| **HMDA DPMS AutoDCR** (`dpms.hmda.gov.in/AutoDCR.Common2/CitizenSearch/publicsearch.aspx`) | **No CAPTCHA. CURRENT data.** Broad discovery by project type + district (+ mandal/village + date). BP search for Medchal-Malkajgiri 2024–2025 returned 23 real Jan–May 2024 permits, paginated. Rich fields incl. **date embedded in the file number** and **promoter/org names**. | ✅ **Live backbone** |
| **GHMC DPMS AutoDCR** | Works, no CAPTCHA, but **frozen ~2017–2020** (2024–25 filter → 0 rows). | Historical only / dropped from MVP |
| **eodb.ghmc** OC/circle search | **HTTP 500 on every query, even via real browser** — broken server-side. | ❌ Dropped |
| **TG-RERA** (`rerait.telangana.gov.in`) | Public + permissive terms, but **mandatory CAPTCHA** + incomplete TLS chain. Rich promoter/scale data. | Semi-manual enrichment (human-in-loop) |
| **datameet GeoJSON** | GHMC 145 wards / **5 zones** / boundary (2017–18). No circle polygons. `gggodhwani` = mandal/village polygons. | ✅ Territory (zone/district/village) |
| **pgeocode** | Resolves Hyderabad pincodes → locality + coords. | ✅ Coarse geocode anchor |

**MVP scope:** lead with **HMDA growth corridors** (Medchal-Malkajgiri + other live HMDA districts — verify each district's coverage on day 1).

**Scope of coverage (honest framing):** *not* "every building in Hyderabad city" — never realistic from public data. We cover **currently-permitted construction in the HMDA jurisdiction** (Greater Hyderabad + surrounding growth mandals/villages: Shamirpet, Keesara, Medchal, Goudavelle, …). A *jurisdictional* scope, not "a few hubs": within live HMDA districts we ingest the full permit stream; the map surfaces hotspots/corridors so it reads as clusters. Excluded: (a) GHMC-core current permits (moved to BuildNow, not yet cracked; frozen 2017–20 GHMC data can appear as an optional "historical footprint" layer only); (b) informal/unpermitted construction (invisible to any permit source). Communicated via the transparency layer, not hidden.

**Two hard truths baked in:**
1. **Ingestion must be Playwright (headless browser)** — the portals are Telerik/RadAjax apps that 500 on hand-built HTTP posts. Proven working. Fine for weekly batch.
2. A permit ≠ an active site. Lifecycle is **inferred with visible confidence + the rule that produced it**, never asserted.

## Verified ingestion recipe

See [SPIKE_FINDINGS.md](SPIKE_FINDINGS.md) for the full recipe (selectors, JS-set-select trick, readonly-date workaround, fields returned), codified in `pipeline/scrapers/hmda_search.py`.

## Recommended tech stack (free-tier, reliable)

- **Pipeline (Python 3.11+):** Playwright (headless Chromium) for HMDA ingestion; pandas normalize; RapidFuzz entity resolution; SQLite working store.
- **Geocoding:** village/mandal-name → centroid (gggodhwani polygons) + pgeocode pincode anchor + cached Nominatim fallback. Every record carries `geo_confidence`.
- **RERA enrichment (optional, semi-manual):** headed Playwright, human solves CAPTCHA, script captures; cross-check public mirrors. No auto-solver.
- **Output artifacts:** `projects.geojson`, `leads.json`, `meta.json` committed to `data/`.
- **Frontend:** React + Vite + TS, react-leaflet + supercluster, Recharts. Client-side filtering over static artifacts (no backend).
- **Refresh:** GitHub Actions weekly cron runs the pipeline and commits artifacts.
- **Hosting:** Vercel / Netlify (static).

## Layered design

1. **Ingestion** — Playwright HMDA scraper, isolated per (district × type × month), raw HTML cached. RERA harvester separate.
2. **Canonical schema** — one `Project`: id, name, promoter_org, location{district,mandal,village,address_raw}, geo{lat,lng,geo_confidence}, permission_types[], category, scale_proxy, dates{permission(from file no.),oc,rera_reg}, stage{label,confidence,rule_id}, sources[], lead_score. Parse **date from file number**; extract **org names** from applicant.
3. **Entity resolution** — RapidFuzz on promoter + village + file/permit number to merge BP↔OC↔RERA; record conflicting statuses.
4. **Lifecycle (transparent, confidence-scored):** R1 Approved/Pre-construction (BP, no OC); R2 Likely Active (RERA under-construction + recent progress); R3 Likely Active inferred (BP age in window, no OC); R4 Near-Completion/Completed (OC present → demand spent). Each stamped with rule id + confidence + inputs.
5. **Geocoding + spatial** — village/mandal → centroid; attach zone/district; geo_confidence surfaced on map.
6. **Demand intelligence** — cement lead score 0–100 with visible breakdown: `w1·stage-window(peak=approved→pre-OC) + w2·scale_proxy + w3·recency + w4·proximity + w5·promoter-repetition`. Hotspots by corridor/village; promoter leaderboard.
7. **Presentation** — clustered map + dashboard + ranked **lead list scoped to chosen districts/villages**. Per-project **transparency panel** (sources, fetched_at, weekly cadence, stage + geo confidence).

## Milestones (2-week arc) — riskiest unknown already de-risked

- **Days 1–2 (partly DONE):** ingestion proven. Confirm which HMDA districts have live coverage; harden the sweep (pagination, retries, caching); land raw records for 2–3 districts.
- **Days 3–5:** canonical schema + file-no date parsing + org extraction + geocoding → end-to-end real data.
- **Days 6–7:** RERA semi-manual harvest; entity resolution HMDA↔RERA.
- **Days 8–10:** lifecycle rules + confidence + lead score; export artifacts; React map + clustering + filters.
- **Days 11–12:** lead list + territory view + dashboard + transparency panels.
- **Days 13–14:** GitHub Actions cron; deploy; assumptions/limitations doc + architecture diagram + distributor narrative.

## Verification (end-to-end)

- **Ingestion:** re-run HMDA sweep for a district+month; assert N>0 rows, expected columns, date parsed from file number, org names extracted.
- **Pipeline:** schema validation; entity resolution merges a known BP↔OC duplicate; geocode coverage % in `meta.json`; lead-score breakdown sums correctly.
- **Frontend E2E:** load artifacts → clustered pins → filters work → lead list re-ranks on territory change → card shows sources + confidences.
- **Demo proof:** distributor covering Shamirpet/Medchal opens app → top ~20 approved-but-not-yet-OC permits from last quarter, ranked → clicks top lead → sees promoter, scale, stage confidence+rule, source records with last-refresh date.

## Open risks (tracked)

1. **Playwright in CI** — Actions runs Chromium fine; verify cron reliability early.
2. **HMDA district coverage varies** — map coverage per district day 1; scope to live districts, label the rest.
3. **RERA CAPTCHA** → semi-manual; curated sample, not exhaustive — stated as a limitation.
4. **No circle polygons / stale wards** → territory at zone/district/village level.
5. **Portal fragility** (eodb down; GHMC frozen) → cache raw responses, degrade gracefully, show `meta.json` freshness honestly.
6. **Scale proxy weak** from list alone → may need per-permit detail-page fetches (extra Playwright hops) or proxy by project-type/promoter.

# Hyderabad Construction Intelligence Map

A map-based "construction intelligence layer" that turns **public building-permission records** into a **ranked weekly lead list** for small cement distributors in the Hyderabad / Telangana region.

> **Core insight:** cement demand peaks from foundation → structural completion, *before* the Occupancy Certificate. The best lead is a project with a **recent building permission and no OC yet**, weighted by scale and location.

## Status

- ✅ **Data-sourcing feasibility verified** (see [docs/SPIKE_FINDINGS.md](docs/SPIKE_FINDINGS.md)).
- ✅ **Data pipeline built + tested** (17/17): scrape → normalize → resolve → geocode → lifecycle → score → export.
- ✅ **Web app built + verified** (light/dark, 0 console errors): map, filters, lead list, transparency panel, dashboard.
- ✅ **Weekly refresh CI** (`.github/workflows/refresh.yml`) + **Vercel deploy** (`vercel.json`).
- ⏳ **Pending a live HMDA run** to replace the sample data in `data/` with real records (portal was mid-outage during the build; scraper is ready — see "Run the pipeline").

Full plan: [docs/PLAN.md](docs/PLAN.md).

## Verified data reality (short version)

| Source | Status | Role |
|---|---|---|
| **HMDA DPMS AutoDCR** | ✅ Live (2024+), no CAPTCHA, broad discovery | **Backbone** |
| GHMC DPMS AutoDCR | ⚠️ Frozen ~2017–2020 | Historical only |
| eodb.ghmc OC search | ❌ Broken (HTTP 500) | Dropped |
| TG-RERA | 🔒 CAPTCHA-gated | Semi-manual enrichment |

Ingestion is via **Playwright** (headless browser) — the portals are Telerik/RadAjax apps that reject hand-built HTTP posts.

## Repository layout

```
pipeline/              Python batch pipeline (Playwright ingest → … → export)
  scrapers/            one scraper per source (hmda_search.py)
  scrape_hmda.py       multi-district/month sweep → raw records JSONL
  {normalize,resolve,geocode,lifecycle,score,export,run}.py
  geocode_cache.json   internal build cache (Nominatim results)
  tests/               unit + end-to-end tests with real-shaped fixtures
web/                   React + Vite + Leaflet static front-end
  public/data/         published artifacts (single source of truth, served as-is)
docs/                  PLAN.md, SPIKE_FINDINGS.md
```

## Run the pipeline

```bash
pip install -r requirements.txt
python -m playwright install chromium

# 1. Sweep HMDA into raw records (needs the portal reachable)
python -m pipeline.scrape_hmda --districts "Medchal-Malkajgiri,Ranga Reddy" --months 12 \
    --out pipeline/raw_cache/hmda_records.jsonl

# 2. Build artifacts straight into the web app's data dir
#    (normalize -> resolve -> geocode -> lifecycle -> score -> export)
python -m pipeline.run --input pipeline/raw_cache/hmda_records.jsonl --top 500

# 3. View
cd web && npm install && npm run dev
```

Run tests: `python -m pipeline.tests.test_normalize` · `test_pipeline` · `test_export`.

> The pipeline writes its published artifacts directly to **`web/public/data/*.json`**
> (single source of truth — the static site serves them as-is). The sample data
> currently in the repo is a small real-shaped fixture; replace it with a live
> sweep (step 1). `pipeline/geocode_cache.json` is an internal build cache.

## Deploy

Static site via **Vercel** (`vercel.json` builds `web/` → `web/dist`). Data refreshes
**weekly** via GitHub Actions (`.github/workflows/refresh.yml`): sweep → pipeline →
commit updated artifacts (Vercel redeploys on the commit).

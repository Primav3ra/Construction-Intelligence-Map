# pipeline/

Python batch pipeline: **Playwright ingest → normalize → entity-resolve → geocode → lifecycle → lead-score → export** to `../data/`.

Modules:
- `scrapers/hmda_search.py` — HMDA AutoDCR ingestion (Playwright); verified live.
- `scrape_hmda.py` — multi-district/month sweep → raw records JSONL.
- `normalize.py` · `resolve.py` (RapidFuzz) · `geocode.py` · `lifecycle.py` · `score.py` · `export.py`
- `run.py` — orchestrates the full chain; `tests/` — unit + e2e.

Published artifacts are written to `web/public/data/`. `geocode_cache.json` is an
internal cache. Raw scraped HTML is cached under `raw_cache/` (gitignored).

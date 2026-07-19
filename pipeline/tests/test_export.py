"""Full-pipeline artifact test: runs raw JSONL -> artifacts offline and validates
the GeoJSON / leads / meta outputs. Run: python -m pipeline.tests.test_export
"""
from __future__ import annotations

import json
import tempfile
from datetime import date
from pathlib import Path

from pipeline.run import run_pipeline

FIXTURE = Path(__file__).parent / "fixtures" / "hmda_resolve_sample.jsonl"
AS_OF = date(2026, 7, 19)


def _run(tmp: Path):
    return run_pipeline(FIXTURE, out_dir=tmp, as_of=AS_OF, allow_network=False,
                        cache_path=tmp / "geocode_cache.json",
                        generated_at="2026-07-19T09:00:00", top_n=100)


def test_artifacts_written_and_valid():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        projects, paths = _run(tmp)
        assert paths["projects"].exists() and paths["leads"].exists() and paths["meta"].exists()

        gj = json.loads(paths["projects"].read_text(encoding="utf-8"))
        assert gj["type"] == "FeatureCollection"
        assert len(gj["features"]) == len(projects), "all projects geocoded (district fallback)"
        for f in gj["features"]:
            lng, lat = f["geometry"]["coordinates"]
            assert 76 < lng < 80 and 15 < lat < 19, f"coords out of Telangana range: {lng},{lat}"
            props = f["properties"]
            assert props["stage"] and "lead_score" in props and props["score_breakdown"]


def test_leads_sorted_desc():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        _run(tmp)
        leads = json.loads((tmp / "leads.json").read_text(encoding="utf-8"))
        scores = [l["lead_score"] for l in leads]
        assert scores == sorted(scores, reverse=True), "leads must be ranked high->low"
        # a completed project should not top the list
        assert leads[0]["stage"] in ("likely_active", "approved")


def test_meta_summary():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        projects, _ = _run(tmp)
        meta = json.loads((tmp / "meta.json").read_text(encoding="utf-8"))
        assert meta["record_count"] == len(projects)
        assert meta["refresh_cadence"] == "weekly"
        assert sum(meta["by_stage"].values()) == len(projects)
        assert meta["geo_coverage_pct"] == 100.0  # district fallback covers all
        assert "hmda_autodcr" in meta["sources"]
        assert "INFERRED" in meta["disclaimer"]


def _run_tests() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t(); print(f"  PASS  {t.__name__}")
        except AssertionError as e:
            failed += 1; print(f"  FAIL  {t.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1; print(f"  ERROR {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_run_tests())

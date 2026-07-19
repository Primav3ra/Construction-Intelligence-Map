"""End-to-end analytical-core test: normalize -> resolve -> lifecycle -> score,
against a fixture of real-shaped HMDA records exercising each rule.

Run:  python -m pipeline.tests.test_pipeline
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from pipeline.normalize import normalize_batch, load_jsonl
from pipeline.resolve import resolve
from pipeline.lifecycle import apply_lifecycle, classify, LifecycleConfig
from pipeline.score import score_batch, rank

FIXTURE = Path(__file__).parent / "fixtures" / "hmda_resolve_sample.jsonl"
AS_OF = date(2026, 7, 19)


def _pipeline():
    projects = normalize_batch(load_jsonl(FIXTURE))
    resolved = resolve(projects)
    apply_lifecycle(resolved, as_of=AS_OF)
    score_batch(resolved, as_of=AS_OF)
    return projects, resolved


def test_normalize_count():
    projects = normalize_batch(load_jsonl(FIXTURE))
    assert len(projects) == 6, f"expected 6 normalized, got {len(projects)}"


def test_resolution_merges_bp_and_oc_via_cross_reference():
    _, resolved = _pipeline()
    # KAKATIYA BP (file 013944...) + OC (permit_number -> 013944...) => one project
    assert len(resolved) == 5, f"expected 5 resolved (BP+OC merged), got {len(resolved)}"
    kak = [p for p in resolved if "KAKATIYA" in p.promoter_org.upper()]
    assert len(kak) == 1, "KAKATIYA BP+OC should merge into one"
    k = kak[0]
    assert len(k.sources) == 2, "merged project keeps both source refs"
    assert k.permission_date == "2018-07-21" and k.oc_date == "2023-09-18"
    assert set(k.permission_types) == {"building_permission", "occupancy_certificate"}


def test_two_buildings_same_builder_same_village_not_merged():
    _, resolved = _pipeline()
    veda = [p for p in resolved if "SRI VEDA" in p.promoter_org.upper()]
    assert len(veda) == 2, "two distinct SRI VEDA building permits must stay separate"


def test_lifecycle_stages():
    _, resolved = _pipeline()
    by_village = {}
    for p in resolved:
        by_village.setdefault(p.village, []).append(p)
    # KAKATIYA (has OC) -> completed
    kak = next(p for p in resolved if "KAKATIYA" in p.promoter_org.upper())
    assert kak.stage == "completed" and kak.stage_rule == "R4:oc_present"
    # recent 2026-04 permit -> approved
    ramesh = next(p for p in resolved if "RAMESH" in p.promoter_org.upper())
    assert ramesh.stage == "approved", ramesh.stage
    # 2024-05/06 permits (~26mo) -> likely_active
    veda = [p for p in resolved if "SRI VEDA" in p.promoter_org.upper()]
    assert all(p.stage == "likely_active" for p in veda), [p.stage for p in veda]
    # 2019-01 permit, no OC (~90mo) -> stale_unknown
    latha = next(p for p in resolved if "LATHA" in p.promoter_org.upper())
    assert latha.stage == "stale_unknown", latha.stage


def test_scoring_priorities():
    _, resolved = _pipeline()
    ranked = rank(resolved)
    # completed project should not be the top lead; an active/approved one should
    top = ranked[0]
    assert top.stage in ("likely_active", "approved"), top.stage
    kak = next(p for p in resolved if "KAKATIYA" in p.promoter_org.upper())
    assert kak.lead_score < top.lead_score, "completed (demand spent) must rank below active"
    # promoter repetition: SRI VEDA appears twice -> nonzero promoter_rep factor
    veda = [p for p in resolved if "SRI VEDA" in p.promoter_org.upper()][0]
    assert veda.score_breakdown["promoter_rep"] > 0.0
    # every scored project exposes a breakdown for the transparency panel
    for p in resolved:
        assert set(p.score_breakdown) == {"stage", "recency", "scale", "proximity", "promoter_rep"}
        assert 0 <= (p.lead_score or 0) <= 100


def test_territory_proximity():
    _, resolved = _pipeline()
    # scoring with a territory limited to Korremul should boost Korremul projects' proximity
    score_batch(resolved, as_of=AS_OF, territory={"villages": ["Korremul"]})
    korremul = [p for p in resolved if p.village == "Korremul"]
    other = [p for p in resolved if p.village != "Korremul"]
    assert all(p.score_breakdown["proximity"] == 1.0 for p in korremul)
    assert all(p.score_breakdown["proximity"] < 1.0 for p in other)


def test_classify_is_pure():
    _, resolved = _pipeline()
    p = resolved[0]
    before = (p.stage, p.stage_confidence, p.stage_rule)
    classify(p, as_of=AS_OF, config=LifecycleConfig())  # returns, does not mutate
    assert (p.stage, p.stage_confidence, p.stage_rule) == before


def _run() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL  {t.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"  ERROR {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_run())

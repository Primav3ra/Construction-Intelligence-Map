"""Tests for normalize.py against a fixture of REAL HMDA records (captured in the spike).

Run directly (no pytest dependency required):
    python -m pipeline.tests.test_normalize
"""
from __future__ import annotations

from pathlib import Path

from pipeline.normalize import (
    normalize_record, normalize_batch, load_jsonl,
    is_organization, clean_org_name, category_and_permission, make_project_id,
)

FIXTURE = Path(__file__).parent / "fixtures" / "hmda_sample.jsonl"


def test_org_detection():
    assert is_organization("DAGPA SUBHAKRITI INFRACON (OPC) PRIVATE LIMITED, Rep by its Directors")
    assert is_organization("M/s. KAKATIYA INFRA PROJECTS Rep. by Its Managing Partner")
    assert is_organization("SAMRUDDHI FOOD GRAIN PROCESSORS Represented By ALAMALAKALA VISHNU MURTHY")
    assert not is_organization("SRI. YADAVALLI VIJAY KUMAR")
    assert not is_organization("GURRAM MADHU AND TWO OTHERS")


def test_clean_org_name_trims_representative_tail():
    n = clean_org_name("DAGPA SUBHAKRITI INFRACON (OPC) PRIVATE LIMITED, Rep by its Directors 1) Sri. X")
    assert n == "DAGPA SUBHAKRITI INFRACON (OPC) PRIVATE LIMITED", n
    n2 = clean_org_name("M/s. KAKATIYA INFRA PROJECTS Rep. by Its Managing Partner Mr. K. VINAY KUMAR")
    assert n2 == "M/s. KAKATIYA INFRA PROJECTS", n2


def test_clean_individual_strips_honorific():
    assert clean_org_name("SRI. YADAVALLI VIJAY KUMAR") == "YADAVALLI VIJAY KUMAR"
    assert clean_org_name("SMT BANOTHU LAXMI") == "BANOTHU LAXMI"


def test_category_and_permission():
    assert category_and_permission("Building Permission") == ("construction", "building_permission")
    assert category_and_permission("Occupancy") == ("occupancy", "occupancy_certificate")
    assert category_and_permission("Layout Open Plot") == ("layout", "layout")


def test_date_routing():
    bp = normalize_record({"file_no": "062254/GHT/R1/U6/HMDA/02012024",
                           "project_type": "Building Permission", "applicant": "SRI. X",
                           "application_date": "2024-01-02", "source": "hmda_autodcr"})
    assert bp.permission_date == "2024-01-02" and bp.oc_date is None

    oc = normalize_record({"file_no": "058812/MED/R1/U6/HMDA/18092023",
                           "project_type": "Occupancy", "applicant": "M/s. KAKATIYA INFRA PROJECTS",
                           "application_date": "2023-09-18", "source": "hmda_autodcr"})
    assert oc.oc_date == "2023-09-18" and oc.permission_date is None
    assert oc.category == "occupancy"


def test_stable_id_and_dedup():
    records = load_jsonl(FIXTURE)
    assert len(records) == 9, f"fixture should have 9 raw rows, got {len(records)}"
    projects = normalize_batch(records)
    # one exact duplicate (062254 appears twice) -> collapses to 8 unique
    assert len(projects) == 8, f"expected 8 unique projects after dedup, got {len(projects)}"
    # id stability
    assert make_project_id("hmda_autodcr", "062254/GHT/R1/U6/HMDA/02012024") == \
           make_project_id("hmda_autodcr", "062254/ght/r1/u6/hmda/02012024")  # case-insensitive
    # dedup keeps the freshest fetched_at
    dup = [p for p in projects if any(s.file_no.startswith("062254") for s in p.sources)]
    assert len(dup) == 1
    assert dup[0].sources[0].fetched_at == "2026-07-19T09:00:00"


def test_full_batch_shape():
    projects = normalize_batch(load_jsonl(FIXTURE))
    orgs = [p for p in projects if p.is_organization]
    indivs = [p for p in projects if not p.is_organization]
    assert len(orgs) >= 3, f"expected >=3 orgs, got {len(orgs)}"
    assert len(indivs) >= 3, f"expected >=3 individuals, got {len(indivs)}"
    # every project has an id, a source, and a category
    for p in projects:
        assert p.project_id and p.sources and p.category
    # occupancy record present and dated
    assert any(p.category == "occupancy" and p.oc_date for p in projects)


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

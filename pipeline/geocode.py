"""Geocode projects to coordinates, with an explicit confidence level.

Village names -> lat/lng via a cached Nominatim (OSM) lookup, falling back to an
approximate HMDA district centroid. Every project records how precise its location
is (``geo_confidence``) so the map can distinguish a real village hit from a coarse
district-centroid placement -- honesty about precision, per the brief.

The cache (committed JSON) means CI and repeat runs don't re-hit Nominatim, and
tests can run fully offline (allow_network=False) against a pre-seeded cache.
"""
from __future__ import annotations

import json
import math
import time
from pathlib import Path

import httpx

from .schema import Project

# A village hit further than this from its district centroid is almost certainly a
# same-name village elsewhere in Telangana (observed: a wrong "Pudoor" ~106km away).
MAX_VILLAGE_KM = 45.0

# Internal build cache (not a published artifact) — kept beside the pipeline code.
CACHE_PATH = Path(__file__).resolve().parent / "geocode_cache.json"
NOMINATIM = "https://nominatim.openstreetmap.org/search"
UA = "hyd-construction-intel/0.1 (hackathon prototype; contact via repo)"

# Approximate centroids for HMDA-jurisdiction districts (fallback only).
DISTRICT_CENTROIDS: dict[str, tuple[float, float]] = {
    "medchal-malkajgiri": (17.6300, 78.4800),
    "hyderabad": (17.3850, 78.4867),
    "ranga reddy": (17.2000, 78.2000),
    "sanga reddy": (17.6200, 78.0800),
    "sangareddy": (17.6200, 78.0800),
    "medak district": (18.0450, 78.2600),
    "medak": (18.0450, 78.2600),
    "siddipet": (18.1010, 78.8520),
    "yadadri": (17.5900, 78.9500),
    "nalgonda": (17.0575, 79.2670),
    "mahaboobnagar": (16.7480, 77.9860),
}


def _key(village: str, district: str) -> str:
    return f"{(village or '').strip().lower()}|{(district or '').strip().lower()}"


def load_cache(path: Path = CACHE_PATH) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def save_cache(cache: dict, path: Path = CACHE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, indent=1, sort_keys=True), encoding="utf-8")


def _haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    (la1, lo1), (la2, lo2) = a, b
    r = 6371.0
    p1, p2 = math.radians(la1), math.radians(la2)
    dp, dl = math.radians(la2 - la1), math.radians(lo2 - lo1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def _clean_village_for_query(village: str) -> str:
    """Real names carry suffixes that break geocoding, e.g. 'Shamirpet-ORRGC',
    'Achampet (Yeldurthy Mandal)'. Reduce to the core place name for the query."""
    import re
    v = re.sub(r"\(.*?\)", "", village or "")     # drop parentheticals
    v = re.split(r"[-,/]", v)[0]                   # take token before - , /
    return v.strip()


def _nominatim_lookup(village: str, district: str) -> tuple[float, float] | None:
    # progressively looser; the caller sanity-checks distance to reject namesakes.
    v = _clean_village_for_query(village)
    for q in (f"{v}, {district}, Telangana",
              f"{v}, Telangana, India"):
        try:
            r = httpx.get(NOMINATIM,
                          params={"q": q, "format": "json", "limit": 1, "countrycodes": "in"},
                          headers={"User-Agent": UA}, timeout=20)
            data = r.json()
            if data:
                return float(data[0]["lat"]), float(data[0]["lon"])
        except Exception:  # noqa: BLE001
            pass
        time.sleep(1.1)  # OSM usage policy
    return None


def geocode_one(village: str, district: str, cache: dict, *,
                allow_network: bool = True, rate_limit_s: float = 1.1
                ) -> tuple[float | None, float | None, str]:
    """Return (lat, lng, geo_confidence). Uses/updates ``cache`` in place."""
    k = _key(village, district)
    if k in cache:
        c = cache[k]
        return c.get("lat"), c.get("lng"), c.get("conf", "none")

    cen = DISTRICT_CENTROIDS.get((district or "").strip().lower())

    if village and allow_network:
        hit = _nominatim_lookup(village, district)
        if hit:
            # reject far-away same-name villages: keep only hits near the district
            if cen is None or _haversine_km(hit, cen) <= MAX_VILLAGE_KM:
                cache[k] = {"lat": hit[0], "lng": hit[1], "conf": "village"}
                return hit[0], hit[1], "village"

    # fallback: district centroid
    if cen:
        cache[k] = {"lat": cen[0], "lng": cen[1], "conf": "district"}
        return cen[0], cen[1], "district"

    cache[k] = {"lat": None, "lng": None, "conf": "none"}
    return None, None, "none"


def geocode_batch(projects: list[Project], *, cache_path: Path = CACHE_PATH,
                  allow_network: bool = True) -> list[Project]:
    cache = load_cache(cache_path)
    for p in projects:
        p.lat, p.lng, p.geo_confidence = geocode_one(
            p.village, p.district, cache, allow_network=allow_network)
    save_cache(cache, cache_path)
    return projects

"""
Google Trends wrapper with daily file cache.

Falls back gracefully to a neutral signal (index=50, direction="flat") if
the API is unavailable, rate-limited, or the category has no keyword mapping.
"""

import json
import warnings
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from config import CATEGORY_TREND_KEYWORDS, TRENDS_CACHE_HOURS, TRENDS_CACHE_PATH


_NEUTRAL = {"index": 50, "direction": "flat"}


def get_category_trend(category: str, cache_path: str = TRENDS_CACHE_PATH) -> dict:
    """
    Return {"index": 0–100, "direction": "rising"|"flat"|"falling"} for a
    category. Reads from cache if fresh; otherwise fetches from Google Trends.
    """
    keyword = CATEGORY_TREND_KEYWORDS.get(category)
    if not keyword:
        return _NEUTRAL

    cache = _load_cache(cache_path)

    if _cache_is_fresh(cache, category, TRENDS_CACHE_HOURS):
        return cache[category]

    result = _fetch_trend(keyword)
    cache[category] = {**result, "fetched_at": datetime.utcnow().isoformat()}
    _save_cache(cache, cache_path)
    return result


def enrich_dataframe(df: pd.DataFrame, cache_path: str = TRENDS_CACHE_PATH) -> pd.DataFrame:
    """Add search_trend_index and trend_direction columns to a per-SKU DataFrame."""
    df = df.copy()
    categories = df["category"].unique()

    trend_map = {cat: get_category_trend(cat, cache_path) for cat in categories}

    df["search_trend_index"] = df["category"].map(
        lambda c: trend_map.get(c, _NEUTRAL)["index"]
    )
    df["trend_direction"] = df["category"].map(
        lambda c: trend_map.get(c, _NEUTRAL)["direction"]
    )
    return df


# ── internals ─────────────────────────────────────────────────────────────────

def _fetch_trend(keyword: str) -> dict:
    try:
        from pytrends.request import TrendReq

        pytrends = TrendReq(hl="en-US", tz=360)
        pytrends.build_payload([keyword], timeframe="today 3-m")
        raw = pytrends.interest_over_time()

        if raw.empty or keyword not in raw.columns:
            return _NEUTRAL

        values = raw[keyword].dropna().tolist()
        if not values:
            return _NEUTRAL

        current = int(values[-1])
        avg = sum(values) / len(values)
        recent_avg = sum(values[-4:]) / max(len(values[-4:]), 1)

        if recent_avg > avg * 1.10:
            direction = "rising"
        elif recent_avg < avg * 0.90:
            direction = "falling"
        else:
            direction = "flat"

        return {"index": current, "direction": direction}

    except Exception as exc:
        warnings.warn(f"Google Trends fetch failed for '{keyword}': {exc}. Using neutral signal.")
        return _NEUTRAL


def _load_cache(path: str) -> dict:
    p = Path(path)
    if p.exists():
        try:
            return json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_cache(data: dict, path: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2))


def _cache_is_fresh(cache: dict, category: str, max_age_hours: int) -> bool:
    if category not in cache:
        return False
    fetched_at = cache[category].get("fetched_at")
    if not fetched_at:
        return False
    age = datetime.utcnow() - datetime.fromisoformat(fetched_at)
    return age < timedelta(hours=max_age_hours)

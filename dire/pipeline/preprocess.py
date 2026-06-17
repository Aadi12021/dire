"""
Preprocess: transforms the multi-row ingested DataFrame into two outputs:
  - df_sku:   one row per SKU, fully featured (used by stages 1, 3, 4)
  - df_store: one row per (sku_id, store_id), velocity features (used by stage 2)
"""

from __future__ import annotations

import calendar
from datetime import date

import pandas as pd

from config import CATEGORY_SEASONS, DEFAULT_SEASON_END_MONTH
from pipeline.features.stubs import make_stub_row
from pipeline.features.velocity import (
    compute_days_in_stock,
    compute_forecast_confidence,
    compute_velocity,
    compute_velocity_change_rate,
)

_SELL_THROUGH_NULL_DEFAULT = 0.0
_DAYS_SINCE_SALE_NULL_DEFAULT = 999


def preprocess(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Returns (df_sku, df_store).
    df_sku  — one row per SKU, all features needed by stage logic.
    df_store — one row per (sku_id, store_id) with per-store velocity.
    """
    max_date = df["date"].max()

    df_sku = _build_sku_features(df, max_date)
    df_store = _build_store_features(df, max_date)

    return df_sku.reset_index(drop=True), df_store.reset_index(drop=True)


# ── SKU-level aggregation ─────────────────────────────────────────────────────

def _build_sku_features(df: pd.DataFrame, max_date: pd.Timestamp) -> pd.DataFrame:
    # Core per-SKU aggregation
    rows = [_aggregate_sku(group, max_date) for _, group in df.groupby("sku_id", sort=False)]
    df_sku = pd.DataFrame(rows)

    # Velocity features (need full df for window calculations)
    v30 = compute_velocity(df, 30)
    v90 = compute_velocity(df, 90)
    vcr = compute_velocity_change_rate(v30, v90)
    confidence = compute_forecast_confidence(df)
    days_in_stock = compute_days_in_stock(df)

    df_sku = (
        df_sku
        .merge(v30.rename("velocity_30d").reset_index(), on="sku_id", how="left")
        .merge(v90.rename("velocity_90d").reset_index(), on="sku_id", how="left")
        .merge(vcr.reset_index(), on="sku_id", how="left")
        .merge(confidence.reset_index(), on="sku_id", how="left")
        .merge(days_in_stock.reset_index(), on="sku_id", how="left")
    )

    df_sku["velocity_change_rate"] = df_sku["velocity_change_rate"].fillna(0.0)
    df_sku["forecast_confidence"] = df_sku["forecast_confidence"].fillna(0.3)

    # Season and urgency
    df_sku["days_until_season_end"] = df_sku.apply(
        lambda r: _days_until_season_end(r["category"], max_date), axis=1
    )
    df_sku["urgency_tier"] = df_sku.apply(_compute_urgency_tier, axis=1)

    # Stub fields — list-valued defaults must be replicated per row
    stub_defaults = make_stub_row()
    n = len(df_sku)
    for col, val in stub_defaults.items():
        if col not in df_sku.columns:
            df_sku[col] = [list(val) if isinstance(val, list) else val for _ in range(n)]

    return _clip_and_fill(df_sku)


def _aggregate_sku(group: pd.DataFrame, max_date: pd.Timestamp) -> dict:
    total_sold = group["units_sold"].sum()
    max_inventory = group["units_on_hand"].max()
    units_received = max_inventory + total_sold
    sell_through = float(total_sold / units_received) if units_received > 0 else None

    sold_mask = group["units_sold"] > 0
    if sold_mask.any():
        last_sale_date = group.loc[sold_mask, "date"].max()
        days_since = int((max_date - last_sale_date).days)
    else:
        days_since = None

    latest = group.sort_values("date").iloc[-1]

    return {
        "sku_id":                  latest["sku_id"],
        "category":                latest["category"],
        "current_price":           latest["current_price"],
        "units_on_hand":           int(latest["units_on_hand"]),
        "cost":                    latest["cost"],
        "original_price":          latest["original_price"],
        "esg_reporting_pressure":  bool(latest["esg_reporting_pressure"]),
        "sell_through_rate":       sell_through,
        "days_since_last_sale":    days_since,
    }


# ── Store-level aggregation (for Stage 2) ─────────────────────────────────────

def _build_store_features(df: pd.DataFrame, max_date: pd.Timestamp) -> pd.DataFrame:
    if "store_id" not in df.columns:
        return pd.DataFrame(columns=["sku_id", "store_id", "velocity_30d", "units_on_hand"])

    rows = []
    for (sku_id, store_id), group in df.groupby(["sku_id", "store_id"], sort=False):
        total_sold = group["units_sold"].sum()
        span_days = max((group["date"].max() - group["date"].min()).days, 1)
        velocity = total_sold / span_days
        latest = group.sort_values("date").iloc[-1]
        rows.append({
            "sku_id":       sku_id,
            "store_id":     store_id,
            "velocity_30d": velocity,
            "units_on_hand": int(latest["units_on_hand"]),
            "sell_through_rate": total_sold / (group["units_on_hand"].max() + total_sold)
                                  if (group["units_on_hand"].max() + total_sold) > 0 else 0.0,
        })
    return pd.DataFrame(rows)


# ── Derived features ──────────────────────────────────────────────────────────

def _days_until_season_end(category: str, ref_date: pd.Timestamp) -> int:
    start_m, end_m = CATEGORY_SEASONS.get(category, (1, DEFAULT_SEASON_END_MONTH))
    ref = ref_date.date() if hasattr(ref_date, "date") else ref_date
    year = ref.year

    season_end = date(year, end_m, calendar.monthrange(year, end_m)[1])
    if season_end < ref:
        # Season already ended this year — use next year's end
        season_end = date(year + 1, end_m, calendar.monthrange(year + 1, end_m)[1])

    return (season_end - ref).days


def _compute_urgency_tier(row: pd.Series) -> str:
    """
    green  — on track, positive momentum
    yellow — slightly behind, gradual slowdown
    orange — meaningfully behind, stagnant
    red    — severely behind, long stagnation
    """
    from config import CLIENTS
    expected = CLIENTS["default"]["expected_sell_through"]
    st = row.get("sell_through_rate", 0.0)
    days = row.get("days_since_last_sale", 0)
    vcr = row.get("velocity_change_rate", 0.0)

    ratio = st / expected if expected > 0 else 0.0

    if ratio >= 1.0 and vcr >= 0:
        return "green"
    if ratio >= 0.6 and days < 30:
        return "yellow"
    if ratio >= 0.3 or days < 45:
        return "orange"
    return "red"


def _clip_and_fill(df: pd.DataFrame) -> pd.DataFrame:
    df["sell_through_rate"] = (
        df["sell_through_rate"].clip(0.0, 1.0).fillna(_SELL_THROUGH_NULL_DEFAULT)
    )
    df["days_since_last_sale"] = (
        df["days_since_last_sale"].clip(0, 9999).fillna(_DAYS_SINCE_SALE_NULL_DEFAULT).astype(int)
    )
    df["velocity_30d"] = df["velocity_30d"].fillna(0.0)
    df["velocity_90d"] = df["velocity_90d"].fillna(0.0)
    return df

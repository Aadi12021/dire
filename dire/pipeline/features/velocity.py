"""
Sales velocity features computed from the date-level ingested DataFrame.

All functions operate on the multi-row (per-date) ingested df, not the
aggregated per-SKU df, so they have access to the full time series.
"""

import pandas as pd


def compute_velocity(df: pd.DataFrame, window_days: int) -> pd.Series:
    """
    Average daily units sold over the last `window_days` days per SKU,
    measured back from the dataset's max date.

    Returns a Series indexed by sku_id.
    """
    max_date = df["date"].max()
    cutoff = max_date - pd.Timedelta(days=window_days)
    window_df = df[df["date"] > cutoff]

    if window_df.empty:
        return pd.Series(dtype=float)

    total_sold = window_df.groupby("sku_id")["units_sold"].sum()
    # Actual span of dates available for each SKU in the window
    date_span = window_df.groupby("sku_id")["date"].nunique().clip(lower=1)
    return (total_sold / date_span).rename(f"velocity_{window_days}d")


def compute_velocity_change_rate(
    velocity_short: pd.Series, velocity_long: pd.Series
) -> pd.Series:
    """
    Rate of change: (short_velocity - long_velocity) / long_velocity.

    Positive  → accelerating (momentum, hold)
    Negative  → decelerating (inventory dying)
    NaN       → insufficient data; treated as 0.0 downstream.
    """
    combined = pd.DataFrame({"short": velocity_short, "long": velocity_long})
    rate = (combined["short"] - combined["long"]) / combined["long"].replace(0, float("nan"))
    return rate.fillna(0.0).rename("velocity_change_rate")


def compute_forecast_confidence(df: pd.DataFrame) -> pd.Series:
    """
    Per-SKU forecast confidence [0, 1] based on consistency of daily sales.

    Uses coefficient of variation (CV = std / mean).
    Low CV  → consistent → high confidence
    High CV → erratic   → low confidence
    < 14 data points    → 0.3 (not enough history)
    Zero sales history  → 0.5 (unknown demand pattern)
    """
    def _sku_confidence(group: pd.DataFrame) -> float:
        if len(group) < 14:
            return 0.3
        mean = group["units_sold"].mean()
        if mean == 0:
            return 0.5
        cv = group["units_sold"].std() / mean
        return float(max(0.0, min(1.0, 1.0 - cv / 2.0)))

    return (
        df.groupby("sku_id")
        .apply(_sku_confidence, include_groups=False)
        .rename("forecast_confidence")
    )


def compute_days_in_stock(df: pd.DataFrame) -> pd.Series:
    """Days from a SKU's first appearance in the dataset to the max date."""
    max_date = df["date"].max()
    first_seen = df.groupby("sku_id")["date"].min()
    return ((max_date - first_seen).dt.days).rename("days_in_stock")

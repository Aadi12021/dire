import pandas as pd
import streamlit as st

_TIER_COLORS = {"green": "🟢", "yellow": "🟡", "orange": "🟠", "red": "🔴"}


def render(df: pd.DataFrame) -> None:
    intervened = df[df["recommendation"] != "hold"]
    total = len(df)
    intervened_count = len(intervened)
    intervened_pct = intervened_count / total * 100 if total > 0 else 0
    dead_value = (intervened["units_on_hand"] * intervened["current_price"]).sum()
    avg_score = df["sustainability_score"].mean()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total SKUs Analyzed", total)
    c2.metric("SKUs Requiring Action", f"{intervened_count} ({intervened_pct:.0f}%)")
    c3.metric("At-Risk Inventory Value", f"${dead_value:,.0f}")
    c4.metric("Avg Sustainability Score", f"{avg_score:.0f} / 100")

    # Urgency tier breakdown
    st.markdown("**Urgency Distribution**")
    tier_counts = df["urgency_tier"].value_counts()
    cols = st.columns(4)
    for col, tier in zip(cols, ["green", "yellow", "orange", "red"]):
        count = tier_counts.get(tier, 0)
        col.metric(f"{_TIER_COLORS[tier]} {tier.capitalize()}", count)

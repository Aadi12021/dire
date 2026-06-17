import pandas as pd
import streamlit as st

from pipeline.explain import explain_sku

# "retailer" is only present in All Retailers combined view — skipped if absent
_DISPLAY_COLS = [
    "retailer",
    "sku_id", "category", "urgency_tier", "recommendation",
    "units_on_hand", "current_price", "sell_through_rate",
    "days_since_last_sale", "velocity_30d", "velocity_change_rate",
    "days_until_season_end", "stage_exit", "sustainability_score",
    "recommended_discount_pct", "redistribution_destination",
    "recommendation_detail", "stub_warnings",
]

_COL_LABELS = {
    "retailer":                   "Retailer",
    "sku_id":                     "SKU",
    "category":                   "Category",
    "urgency_tier":               "Urgency",
    "recommendation":             "Recommendation",
    "units_on_hand":              "Units on Hand",
    "current_price":              "Price",
    "sell_through_rate":          "Sell-Through",
    "days_since_last_sale":       "Days Stagnant",
    "velocity_30d":               "30d Velocity",
    "velocity_change_rate":       "Velocity Δ",
    "days_until_season_end":      "Days to Season End",
    "stage_exit":                 "Stage",
    "sustainability_score":       "ESG Score",
    "recommended_discount_pct":   "Discount %",
    "redistribution_destination": "Reroute To",
    "recommendation_detail":      "Detail",
    "stub_warnings":              "Data Gaps",
}


def render(df: pd.DataFrame) -> None:
    with st.sidebar:
        st.subheader("Filters")

        categories = ["All"] + sorted(df["category"].unique().tolist())
        selected_category = st.selectbox("Category", categories)

        tiers = ["All"] + ["red", "orange", "yellow", "green"]
        selected_tier = st.selectbox("Urgency Tier", tiers)

        recs = ["All"] + sorted(df["recommendation"].unique().tolist())
        selected_rec = st.selectbox("Recommendation", recs)

        min_units = st.number_input("Min Units on Hand", min_value=0, value=0, step=1)

    filtered = df.copy()
    if selected_category != "All":
        filtered = filtered[filtered["category"] == selected_category]
    if selected_tier != "All":
        filtered = filtered[filtered["urgency_tier"] == selected_tier]
    if selected_rec != "All":
        filtered = filtered[filtered["recommendation"] == selected_rec]
    filtered = filtered[filtered["units_on_hand"] >= min_units]

    st.caption(f"{len(filtered)} of {len(df)} SKUs shown")

    available = [c for c in _DISPLAY_COLS if c in filtered.columns]
    display = filtered[available].rename(columns=_COL_LABELS)
    st.dataframe(display, use_container_width=True, hide_index=True)

    csv = filtered[available].to_csv(index=False)
    st.download_button(
        label="Download filtered results as CSV",
        data=csv,
        file_name="dire_results.csv",
        mime="text/csv",
    )

    st.divider()

    # ── AI Explanations ───────────────────────────────────────────────────────
    api_key = st.session_state.get("anthropic_api_key", "")
    if not api_key:
        st.caption("Set an Anthropic API key in **Settings** to enable AI explanations.")
    else:
        explanations = st.session_state.get("explanations", {})
        already_done = filtered["sku_id"].isin(explanations).sum()
        to_generate = len(filtered) - already_done

        btn_label = (
            f"Generate AI Explanations ({to_generate} new)"
            if to_generate > 0 else "Explanations generated for all filtered SKUs"
        )
        if st.button(btn_label, disabled=(to_generate == 0)):
            rows_to_explain = filtered[~filtered["sku_id"].isin(explanations)].to_dict("records")
            progress = st.progress(0)
            for i, row in enumerate(rows_to_explain):
                try:
                    explanations[row["sku_id"]] = explain_sku(row, api_key)
                except Exception as e:
                    explanations[row["sku_id"]] = f"Could not generate explanation: {e}"
                progress.progress((i + 1) / len(rows_to_explain))
            st.session_state["explanations"] = explanations
            st.success(f"Generated {len(rows_to_explain)} explanation(s).")
            st.rerun()

    # Display cached explanations for SKUs currently in view
    explanations = st.session_state.get("explanations", {})
    skus_in_view = set(filtered["sku_id"].tolist())
    cached = {sku: txt for sku, txt in explanations.items() if sku in skus_in_view}
    if cached:
        st.subheader("AI Explanations")
        for sku_id, explanation in cached.items():
            row_data = filtered[filtered["sku_id"] == sku_id]
            if row_data.empty:
                continue
            r = row_data.iloc[0]
            label = f"{sku_id} — {r['recommendation'].upper()} ({r['urgency_tier']})"
            with st.expander(label):
                st.write(explanation)

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

_ACTION_COLORS = {
    "hold":         "#2ecc71",
    "redistribute": "#3498db",
    "markdown":     "#f39c12",
    "marketplace":  "#e67e22",
    "donate":       "#9b59b6",
    "recycle":      "#1abc9c",
    "liquidate":    "#e74c3c",
}

_TIER_COLORS = {
    "green":  "#2ecc71",
    "yellow": "#f1c40f",
    "orange": "#e67e22",
    "red":    "#e74c3c",
}


def render(df: pd.DataFrame) -> None:
    left, right = st.columns(2)

    with left:
        st.subheader("Recommendation Breakdown")
        counts = df["recommendation"].value_counts().reset_index()
        counts.columns = ["recommendation", "count"]
        fig = px.bar(
            counts, x="recommendation", y="count",
            color="recommendation",
            color_discrete_map=_ACTION_COLORS,
            labels={"recommendation": "Recommendation", "count": "SKU Count"},
        )
        fig.update_layout(showlegend=False, xaxis_title=None)
        st.plotly_chart(fig, use_container_width=True)

    with right:
        st.subheader("Urgency Tier Distribution")
        tier_counts = df["urgency_tier"].value_counts().reset_index()
        tier_counts.columns = ["tier", "count"]
        tier_order = ["green", "yellow", "orange", "red"]
        tier_counts["tier"] = pd.Categorical(tier_counts["tier"], categories=tier_order, ordered=True)
        tier_counts = tier_counts.sort_values("tier")
        fig = px.bar(
            tier_counts, x="tier", y="count",
            color="tier",
            color_discrete_map=_TIER_COLORS,
            labels={"tier": "Urgency Tier", "count": "SKU Count"},
        )
        fig.update_layout(showlegend=False, xaxis_title=None)
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Sustainability Score by Recommendation")
    fig = px.box(
        df, x="recommendation", y="sustainability_score",
        color="recommendation",
        color_discrete_map=_ACTION_COLORS,
        labels={"recommendation": "Recommendation", "sustainability_score": "Score"},
        points="all",
    )
    fig.update_layout(showlegend=False, xaxis_title=None, yaxis_range=[0, 110])
    st.plotly_chart(fig, use_container_width=True)

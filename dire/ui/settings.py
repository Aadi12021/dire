import os

import streamlit as st

from config import CLIENTS

_DEFAULT = CLIENTS["default"]


def render() -> None:
    st.header("Threshold Settings")
    st.caption(
        "Adjust decision thresholds below, then click **Apply & Re-run** "
        "to update results for all loaded retailers."
    )

    override = st.session_state.get("config_override", {})

    st.subheader("Intervention Thresholds")
    c1, c2 = st.columns(2)

    with c1:
        intervention_days = st.slider(
            "Days stagnant before intervention",
            min_value=14, max_value=120, step=1,
            value=override.get(
                "intervention_days_stagnant",
                _DEFAULT["intervention_days_stagnant"],
            ),
            help="SKUs with no sales for this many days trigger the pipeline.",
        )
        expected_sell_through_pct = st.slider(
            "Expected sell-through rate",
            min_value=30, max_value=95, step=1,
            value=int(
                override.get("expected_sell_through", _DEFAULT["expected_sell_through"]) * 100
            ),
            format="%d%%",
            help="SKUs below this sell-through rate are flagged for action.",
        )

    with c2:
        markdown_margin_floor_pct = st.slider(
            "Markdown margin floor",
            min_value=5, max_value=30, step=1,
            value=int(
                override.get("markdown_margin_floor", _DEFAULT["markdown_margin_floor"]) * 100
            ),
            format="%d%%",
            help="Minimum acceptable margin after markdown. SKUs breaching this go to marketplace.",
        )
        markdown_max_discount_pct = st.slider(
            "Max markdown discount",
            min_value=10, max_value=60, step=1,
            value=int(
                override.get("markdown_max_discount", _DEFAULT["markdown_max_discount"]) * 100
            ),
            format="%d%%",
            help="Maximum discount depth allowed for markdown recommendations.",
        )

    min_transfer_units = st.slider(
        "Minimum units for redistribution",
        min_value=5, max_value=50, step=1,
        value=override.get("min_transfer_units", _DEFAULT["min_transfer_units"]),
        help="Redistribution only triggers if at least this many units are available.",
    )
    esg_priority = st.toggle(
        "ESG Priority Mode",
        value=bool(override.get("esg_priority", _DEFAULT["esg_priority"])),
        help="When enabled, Stage 4 favours donation and recycling over liquidation.",
    )

    st.divider()
    st.subheader("AI Explanations")
    st.caption(
        "Provide an Anthropic API key to enable per-SKU AI-generated explanations "
        "on the SKU Table view."
    )

    # Resolve key: Streamlit secrets > env var > session input
    env_key = (
        st.secrets.get("ANTHROPIC_API_KEY", "")
        if hasattr(st, "secrets") else ""
    ) or os.environ.get("ANTHROPIC_API_KEY", "")

    if env_key and not st.session_state.get("anthropic_api_key"):
        st.session_state["anthropic_api_key"] = env_key

    stored_key = st.session_state.get("anthropic_api_key", "")

    if env_key:
        st.caption("API key loaded from environment / Streamlit secrets.")
        api_key_input = env_key
    else:
        api_key_input = st.text_input(
            "Anthropic API Key",
            value=stored_key,
            type="password",
            placeholder="sk-ant-...",
            help="Used only for generating explanations in this session. Not stored permanently.",
        )
        if stored_key:
            st.caption("API key is set for this session.")

    st.divider()
    if st.button("Apply & Re-run", type="primary"):
        new_override = {
            "intervention_days_stagnant": intervention_days,
            "expected_sell_through":      expected_sell_through_pct / 100,
            "markdown_margin_floor":      markdown_margin_floor_pct / 100,
            "markdown_max_discount":      markdown_max_discount_pct / 100,
            "min_transfer_units":         min_transfer_units,
            "esg_priority":               esg_priority,
        }
        st.session_state["config_override"] = new_override

        if api_key_input:
            st.session_state["anthropic_api_key"] = api_key_input

        retailers = st.session_state.get("retailers", {})
        if retailers:
            from pipeline.runner import run
            with st.spinner(f"Re-running pipeline for {len(retailers)} retailer(s)..."):
                for name in retailers:
                    retailers[name]["df_output"] = run(
                        retailers[name]["df_raw"],
                        config_override=new_override,
                    )
            st.session_state["retailers"] = retailers
            st.success(
                f"Applied new thresholds and re-ran pipeline for {len(retailers)} retailer(s). "
                "Switch to Dashboard or SKU Table to see updated results."
            )
        else:
            st.success("Settings saved. Load data in Upload to see results.")

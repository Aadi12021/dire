import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

from pipeline.ingest import load
from pipeline.runner import run
from ui import charts, settings, summary, table

_SAMPLE_CSV = Path(__file__).parent / "data" / "fixture.csv"

st.set_page_config(page_title="DIRE", layout="wide")
st.title("DIRE — Dead Inventory Resurrection Engine")

view = st.sidebar.radio("View", ["Upload", "Settings", "Dashboard", "SKU Table"])


def _retailer_selector(key: str) -> tuple[str, pd.DataFrame | None]:
    """Sidebar retailer dropdown. Returns (selected_name, combined_or_single_df)."""
    retailers = st.session_state.get("retailers", {})
    if not retailers:
        return "none", None

    names = list(retailers.keys())
    options = (["All Retailers"] + names) if len(names) > 1 else names
    selected = st.sidebar.selectbox("Retailer", options, key=key)

    if selected == "All Retailers":
        dfs = []
        for name, data in retailers.items():
            df_copy = data["df_output"].copy()
            df_copy.insert(0, "retailer", name)
            dfs.append(df_copy)
        return selected, pd.concat(dfs, ignore_index=True)

    return selected, retailers[selected]["df_output"]


# ── Upload ────────────────────────────────────────────────────────────────────

if view == "Upload":
    st.header("Load Inventory Data")

    uploaded_files = st.file_uploader(
        "Upload Retail Inventory CSV(s)",
        type="csv",
        accept_multiple_files=True,
        help="Each filename becomes the retailer name. Upload multiple files to compare retailers.",
    )

    if uploaded_files:
        config_override = st.session_state.get("config_override")
        retailers = st.session_state.get("retailers", {})
        loaded, errors = [], []
        for f in uploaded_files:
            retailer_name = Path(f.name).stem
            try:
                df_raw = pd.read_csv(f)
                retailers[retailer_name] = {
                    "df_raw": df_raw,
                    "df_output": run(df_raw, config_override=config_override),
                }
                loaded.append(retailer_name)
            except ValueError as e:
                errors.append(f"{retailer_name}: {e}")
        st.session_state["retailers"] = retailers
        if loaded:
            st.success(
                f"Loaded {len(loaded)} retailer(s): {', '.join(loaded)}. "
                "Switch to Dashboard to see results."
            )
        for err in errors:
            st.error(err)

    st.divider()

    if st.button("Load Demo Retailer", type="secondary"):
        config_override = st.session_state.get("config_override")
        df_raw = load(_SAMPLE_CSV)
        retailers = st.session_state.get("retailers", {})
        retailers["Demo Store"] = {
            "df_raw": df_raw,
            "df_output": run(df_raw, config_override=config_override),
        }
        st.session_state["retailers"] = retailers
        n = len(retailers["Demo Store"]["df_output"])
        st.success(f"Demo Store loaded: {n} SKUs. Switch to Dashboard.")

    retailers = st.session_state.get("retailers", {})
    if retailers:
        st.subheader("Loaded Retailers")
        for name, data in list(retailers.items()):
            n = len(data["df_output"])
            col1, col2 = st.columns([4, 1])
            col1.write(f"**{name}** — {n} SKUs")
            if col2.button("Remove", key=f"remove_{name}"):
                del st.session_state["retailers"][name]
                st.rerun()


# ── Settings ──────────────────────────────────────────────────────────────────

elif view == "Settings":
    settings.render()


# ── Guard: no data yet ────────────────────────────────────────────────────────

elif not st.session_state.get("retailers"):
    st.info("Go to **Upload** and load a CSV or click **Load Demo Retailer** to get started.")


# ── Dashboard ─────────────────────────────────────────────────────────────────

elif view == "Dashboard":
    st.header("Dashboard")
    _name, df = _retailer_selector("dashboard_retailer")
    if df is not None:
        summary.render(df)
        st.divider()
        charts.render(df)


# ── SKU Table ─────────────────────────────────────────────────────────────────

elif view == "SKU Table":
    st.header("SKU Results")
    _name, df = _retailer_selector("table_retailer")
    if df is not None:
        table.render(df)

DIRE — Dead Inventory Resurrection Engine
Technical Spec (current as of Week 2)

Stack: Python 3.11+, Pandas, Streamlit, Plotly, Anthropic SDK

---

Directory Structure

dire/
├── app.py                        # Streamlit entry point (4 views, multi-retailer)
├── config.py                     # All thresholds, constants, client profiles
├── requirements.txt              # Pinned deps for Streamlit Cloud deploy
├── data/
│   ├── fixture.csv               # Sample inventory dataset (Kaggle)
│   └── .trends_cache.json        # Google Trends response cache (24h TTL)
├── pipeline/
│   ├── ingest.py                 # Load + validate CSV, map columns to DIRE schema
│   ├── preprocess.py             # Feature engineering (sell-through, days since last sale)
│   ├── runner.py                 # Orchestrates ingest → preprocess → stages → output df
│   ├── explain.py                # Claude API wrapper — per-SKU explanation generation
│   ├── features/
│   │   ├── stubs.py              # Typed stub fields for data not yet available
│   │   ├── trends.py             # Google Trends enrichment (cached)
│   │   └── velocity.py           # Velocity + momentum calculations
│   └── stages/
│       ├── stage1.py             # Intervene? (stagnation + momentum check)
│       ├── stage2.py             # Redistribute? (cross-store demand differential)
│       ├── stage3.py             # Markdown or marketplace? (margin floor logic)
│       └── stage4.py             # Sustainability routing (donate / recycle / liquidate)
└── ui/
    ├── summary.py                # KPI cards + urgency tier breakdown
    ├── table.py                  # Filterable SKU table + AI explanation panel
    ├── charts.py                 # Recommendation breakdown + urgency + ESG charts
    └── settings.py               # Threshold sliders + Anthropic API key input

---

Pipeline Architecture

The pipeline is a 4-stage decision tree. Each SKU exits at the first stage that claims it.

Stage 1 — Intervene?
  Checks sell_through_rate, days_since_last_sale, velocity_change_rate, forecast_confidence.
  If the SKU has positive momentum or is on track → hold (no action).
  Otherwise → pass to Stage 2.

Stage 2 — Redistribute?
  Checks for a destination store with meaningfully higher demand (≥25% velocity differential).
  Requires min_transfer_units available. If a viable transfer exists → redistribute.
  Otherwise → pass to Stage 3.

Stage 3 — Markdown or Marketplace?
  Calculates discount depth from urgency tier, adjusted by trend direction and days to season end.
  If discounted price stays above margin floor → markdown with projected clearance days.
  If margin floor is breached at max discount → marketplace channel.

Stage 4 — Sustainability routing
  ESG priority mode (configurable): donate → recycle → liquidate in that order.
  Default mode: picks whichever action is viable (min unit thresholds apply).

---

config.py

CLIENTS dict holds per-retailer threshold profiles. runner.run() accepts a config_override dict
that gets merged on top of the selected client profile at runtime (used by the Settings UI).

Default client profile:
  intervention_days_stagnant:  45    # days with no sales before pipeline triggers
  expected_sell_through:       0.70  # below this → flagged
  markdown_margin_floor:       0.10  # minimum margin allowed after markdown
  markdown_max_discount:       0.40  # maximum markdown depth
  min_transfer_units:          10    # redistribution only if at least this many units
  esg_priority:                False # True → Stage 4 prefers donate/recycle over liquidate

---

pipeline/runner.py

run(df_raw, client_id="default", config_override=None) -> pd.DataFrame

Merges config_override into the client profile if provided, then runs all 4 stages per SKU.
Stores df_raw in session_state so Settings can re-run the pipeline after threshold changes.

---

pipeline/explain.py

explain_sku(row: dict, api_key: str) -> str

Calls claude-opus-4-8 with a structured prompt (SKU stats + recommendation + detail).
Returns a 2-3 sentence plain-text explanation for store managers.
Results are cached in st.session_state["explanations"] keyed by sku_id.

---

pipeline/features/stubs.py

11 typed stub fields for data not yet available (ERP, pricing API, logistics API):
  discount_history_ever/max_pct/lift, demand_elasticity, perishability_days,
  material_composition, competitor_price, marketplace_sell_through_rate,
  transport_cost_per_unit, transit_time_days, tax_deduction_eligible, bundle_candidates

Stubs return safe defaults and emit warnings when accessed unset. Stage logic reads stubs
and appends warnings to stub_warnings column in the output df.

---

app.py — Streamlit shell

Four views, controlled by sidebar radio:

View 1: Upload
  Multi-file uploader — each filename becomes a retailer name.
  Each file runs the full pipeline with the current config_override.
  "Load Demo Retailer" loads fixture.csv as "Demo Store".
  Loaded retailers listed with SKU count + Remove button.
  Session state: retailers[name] = {df_raw, df_output}

View 2: Settings
  Sliders for all 6 client thresholds (ranges tuned to realistic retail bounds).
  Anthropic API key input — reads from st.secrets / env var first, falls back to text input.
  "Apply & Re-run" re-runs the pipeline for all loaded retailers with new thresholds.

View 3: Dashboard
  Retailer selector (sidebar) — individual retailer or "All Retailers" combined.
  4 KPI cards: Total SKUs, SKUs Requiring Action, At-Risk Inventory Value, Avg ESG Score.
  Urgency tier breakdown (green / yellow / orange / red).
  Recommendation breakdown bar chart + urgency tier bar chart + ESG box plot by action.

View 4: SKU Table
  Retailer selector (same pattern as Dashboard).
  Filters: Category, Urgency Tier, Recommendation, Min Units on Hand.
  "Generate AI Explanations (N new)" button — calls explain_sku() per filtered SKU,
    shows progress bar, caches results, displays in expandable rows below the table.
  Download filtered results as CSV.

---

Data Flow

User uploads CSV(s)
       ↓
ingest.py: validate columns, rename to DIRE schema, type coercion
       ↓
preprocess.py: engineer sell_through_rate, days_since_last_sale, velocity features
       ↓
features/trends.py: attach Google Trends direction signal per category (cached 24h)
       ↓
runner.py: runs each SKU through Stage 1→4, merges results back onto feature df
       ↓
session_state["retailers"][name] = {df_raw, df_output}
       ↓
ui/summary.py    → KPI cards + urgency breakdown
ui/charts.py     → Plotly recommendation + tier + ESG charts
ui/table.py      → filterable table + CSV export + AI explanation panel
ui/settings.py   → threshold sliders, re-runs pipeline on Apply

---

Deployment

requirements.txt is present. Deploy to Streamlit Community Cloud:
  1. Push dire/ to a GitHub repo
  2. New app at share.streamlit.io → main file: dire/app.py
  3. Add ANTHROPIC_API_KEY to Streamlit Cloud secrets (Settings → Secrets)

---

Still Out of Scope

Geographic demand modeling
ERP / API integration (Shopify, NetSuite)
Real stub data (discount history, competitor pricing, logistics costs)
Authentication / multi-user sessions

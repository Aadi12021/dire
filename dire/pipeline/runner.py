"""
Runner — orchestrates the full DIRE pipeline.

    df_raw
      → ingest()          map + validate raw CSV columns
      → preprocess()      engineer features; returns (df_sku, df_store)
      → trends.enrich()   attach Google Trends signals
      → stage loop        evaluate each SKU through stages 1-4
      → df_output         one row per SKU with recommendation + full feature set
"""

import pandas as pd

from config import SUSTAINABILITY_SCORE, get_client
from pipeline.features import trends as trends_module
from pipeline.ingest import ingest
from pipeline.preprocess import preprocess
from pipeline.stages import stage1, stage2, stage3, stage4


def run(
    df_raw: pd.DataFrame,
    client_id: str = "default",
    config_override: dict | None = None,
) -> pd.DataFrame:
    """Full pipeline. Returns one row per SKU with all features and recommendations."""
    client = get_client(client_id)
    if config_override:
        client = {**client, **config_override}

    df_mapped = ingest(df_raw)
    df_sku, df_store = preprocess(df_mapped)
    df_sku = trends_module.enrich_dataframe(df_sku)

    records = []
    for _, row in df_sku.iterrows():
        records.append(_evaluate_sku(row, df_store, client))

    results_df = pd.DataFrame(records)
    return df_sku.merge(results_df, on="sku_id")


# ── per-SKU evaluation ────────────────────────────────────────────────────────

def _evaluate_sku(row: pd.Series, df_store: pd.DataFrame, client: dict) -> dict:
    all_stub_warnings: list[str] = []

    # Stage 1 — intervene?
    s1 = stage1.evaluate(row, client)
    if not s1.should_intervene:
        return _output(row, "hold", s1.reason, 1, SUSTAINABILITY_SCORE["hold"], [])

    # Stage 2 — redistribute?
    s2 = stage2.evaluate(row, df_store, client)
    all_stub_warnings.extend(s2.stub_warnings)
    if s2.should_redistribute:
        return _output(
            row, "redistribute", s2.reason, 2, SUSTAINABILITY_SCORE["redistribute"],
            all_stub_warnings,
            redistribution_destination=s2.destination_store_id,
            demand_differential=s2.demand_differential,
        )

    # Stage 3 — markdown or marketplace?
    s3 = stage3.evaluate(row, client)
    all_stub_warnings.extend(s3.stub_warnings)
    if s3.action in ("markdown", "marketplace"):
        return _output(
            row, s3.action, s3.reason, 3, SUSTAINABILITY_SCORE[s3.action],
            all_stub_warnings,
            recommended_discount_pct=s3.recommended_discount_pct,
            projected_clearance_days=s3.projected_clearance_days,
        )

    # Stage 4 — sustainability routing
    s4 = stage4.evaluate(row, client)
    all_stub_warnings.extend(s4.stub_warnings)
    return _output(
        row, s4.action, s4.reason, 4, SUSTAINABILITY_SCORE[s4.action],
        all_stub_warnings,
        sustainability_partner=s4.partner,
    )


def _output(
    row: pd.Series,
    recommendation: str,
    detail: str,
    stage_exit: int,
    sustainability_score: int,
    stub_warnings: list[str],
    **extra,
) -> dict:
    base = {
        "sku_id":               row["sku_id"],
        "recommendation":       recommendation,
        "recommendation_detail": detail,
        "stage_exit":           stage_exit,
        "sustainability_score": sustainability_score,
        "stub_warnings":        " | ".join(stub_warnings) if stub_warnings else "",
        # Stage-specific extras with safe defaults
        "redistribution_destination": None,
        "demand_differential":        None,
        "recommended_discount_pct":   None,
        "projected_clearance_days":   None,
        "sustainability_partner":     None,
    }
    base.update(extra)
    return base


# ── terminal test entry point ─────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).parent.parent))
    from pipeline.ingest import load

    csv_path = Path(__file__).parent.parent / "data" / "fixture.csv"
    df_output = run(load(csv_path))

    display_cols = [
        "sku_id", "category", "urgency_tier",
        "sell_through_rate", "days_since_last_sale",
        "velocity_30d", "velocity_change_rate",
        "recommendation", "stage_exit", "sustainability_score",
    ]
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 160)
    print(df_output[display_cols].to_string(index=False))
    print("\n--- Recommendation Detail ---")
    for _, r in df_output.iterrows():
        print(f"\n[{r['sku_id']}] {r['recommendation'].upper()}")
        print(f"  {r['recommendation_detail']}")
        if r["stub_warnings"]:
            print(f"  ⚠ Stubs: {r['stub_warnings']}")

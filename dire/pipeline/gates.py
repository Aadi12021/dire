from dataclasses import dataclass

import pandas as pd

from config import SUSTAINABILITY_BASE, THRESHOLDS

_SUSTAINABILITY_DELTA = {
    "healthy": 50,       # 100 total — inventory managed well, no waste
    "markdown": 25,      # 75 total — item still reaches a consumer
    "liquidate_b2b": 5,  # 55 total — bulk move, some environmental cost
    "donate": 30,        # 80 total — good social outcome
    "recycle": -10,      # 40 total — material recovery but energy cost
}


@dataclass
class GateResult:
    sku_id: str
    action: str          # healthy | markdown | liquidate_b2b | donate | recycle
    action_detail: str
    gate_exit: int       # 0 = healthy, 1 = markdown, 2 = B2B, 3 = end-of-life
    sustainability_score: int


def run_pipeline(df: pd.DataFrame) -> list[GateResult]:
    return [_evaluate_sku(row) for _, row in df.iterrows()]


# --- gate logic --------------------------------------------------------------

def _evaluate_sku(row: pd.Series) -> GateResult:
    # Gate 0 — is the SKU dead?
    is_dead = (
        row["sell_through_rate"] < THRESHOLDS["dead_sell_through"]
        and row["days_since_last_sale"] >= THRESHOLDS["dead_days_since_sale"]
    )
    if not is_dead:
        return _result(row["sku_id"], "healthy", "Sell-through and recency within thresholds.", 0)

    # Gate 1 — can a markdown recover it?
    discounted_price = row["current_price"] * (1 - THRESHOLDS["markdown_max_discount"])
    if discounted_price > 0:
        markdown_margin = (discounted_price - row["cost"]) / discounted_price
    else:
        markdown_margin = 0.0

    if markdown_margin >= THRESHOLDS["markdown_margin_floor"]:
        discount_pct = int(THRESHOLDS["markdown_max_discount"] * 100)
        detail = f"Apply up to {discount_pct}% markdown. Margin at floor: {markdown_margin:.0%}."
        return _result(row["sku_id"], "markdown", detail, 1)

    # Gate 2 — B2B liquidation viable?
    if row["current_price"] > 0:
        b2b_margin = (row["current_price"] - row["cost"]) / row["current_price"]
    else:
        b2b_margin = 0.0

    if (
        row["units_on_hand"] >= THRESHOLDS["secondary_min_units"]
        and b2b_margin >= THRESHOLDS["secondary_min_margin"]
    ):
        detail = f"Route {row['units_on_hand']} units to B2B liquidation partner."
        return _result(row["sku_id"], "liquidate_b2b", detail, 2)

    # Gate 3 — end-of-life disposal
    if row["esg_reporting_pressure"]:
        return _result(row["sku_id"], "donate", "Donate to nonprofit/charity for ESG credit.", 3)
    return _result(row["sku_id"], "recycle", "Route to materials recycling program.", 3)


def _result(sku_id: str, action: str, detail: str, gate: int) -> GateResult:
    return GateResult(
        sku_id=sku_id,
        action=action,
        action_detail=detail,
        gate_exit=gate,
        sustainability_score=SUSTAINABILITY_BASE + _SUSTAINABILITY_DELTA[action],
    )

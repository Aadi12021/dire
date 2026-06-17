"""
Stage 2 — Should we redistribute to another store?

Compares origin store velocity against all other stores carrying the same SKU.
Recommends transfer if:
  - A destination store has meaningfully higher demand (velocity differential)
  - Origin has enough units to transfer (min batch threshold)
  - Destination has genuine demand (sell-through above floor)
  - Destination has capacity (not already overstocked)

Transport cost and transit time remain stubs — included in warnings when unset.
"""

from dataclasses import dataclass, field

import pandas as pd

from config import STAGE2


@dataclass
class Stage2Result:
    should_redistribute: bool
    destination_store_id: str | None
    demand_differential: float
    reason: str
    stub_warnings: list[str] = field(default_factory=list)


def evaluate(row: pd.Series, df_store: pd.DataFrame, client: dict) -> Stage2Result:
    sku_id = row["sku_id"]
    units = row["units_on_hand"]

    stub_warnings: list[str] = []
    if row.get("transport_cost_per_unit") is None:
        stub_warnings.append("transport_cost_per_unit not set — margin-after-transport unverified")
    if row.get("transit_time_days") is None:
        stub_warnings.append("transit_time_days not set — lead-time vs season-end unverified")

    # No store-level data available
    if df_store.empty or "store_id" not in df_store.columns:
        return Stage2Result(
            should_redistribute=False,
            destination_store_id=None,
            demand_differential=0.0,
            reason="No store-level data available for redistribution analysis.",
            stub_warnings=stub_warnings,
        )

    # Find all stores carrying this SKU
    sku_stores = df_store[df_store["sku_id"] == sku_id].copy()
    if len(sku_stores) < 2:
        return Stage2Result(
            should_redistribute=False,
            destination_store_id=None,
            demand_differential=0.0,
            reason="SKU only exists at one store — no redistribution target.",
            stub_warnings=stub_warnings,
        )

    # Origin: the store with the lowest sell-through (the dead one)
    origin = sku_stores.sort_values("sell_through_rate").iloc[0]
    origin_velocity = origin["velocity_30d"]

    # Candidate destinations: other stores with higher demand and capacity
    candidates = sku_stores[sku_stores["store_id"] != origin["store_id"]].copy()
    candidates = candidates[
        candidates["sell_through_rate"] > STAGE2["destination_capacity_floor"]
    ]

    if candidates.empty:
        return Stage2Result(
            should_redistribute=False,
            destination_store_id=None,
            demand_differential=0.0,
            reason="No destination store has meaningful demand for this SKU.",
            stub_warnings=stub_warnings,
        )

    best = candidates.sort_values("velocity_30d", ascending=False).iloc[0]
    dest_velocity = best["velocity_30d"]

    differential = (
        (dest_velocity - origin_velocity) / max(origin_velocity, 0.001)
    )

    min_units = max(client["min_transfer_units"], STAGE2["min_transfer_units"])

    if differential < STAGE2["min_demand_differential"]:
        return Stage2Result(
            should_redistribute=False,
            destination_store_id=None,
            demand_differential=differential,
            reason=(
                f"Demand differential {differential:.0%} is below threshold "
                f"({STAGE2['min_demand_differential']:.0%}) — moving inventory "
                "would not meaningfully improve sell-through."
            ),
            stub_warnings=stub_warnings,
        )

    if units < min_units:
        return Stage2Result(
            should_redistribute=False,
            destination_store_id=None,
            demand_differential=differential,
            reason=(
                f"Only {units} units available — below minimum transfer batch ({min_units})."
            ),
            stub_warnings=stub_warnings,
        )

    return Stage2Result(
        should_redistribute=True,
        destination_store_id=str(best["store_id"]),
        demand_differential=differential,
        reason=(
            f"Transfer {units} units to store {best['store_id']}. "
            f"Destination velocity is {differential:.0%} higher than origin."
        ),
        stub_warnings=stub_warnings,
    )

"""
Stage 3 — Markdown or Marketplace?

Recommends a discount depth based on urgency tier, adjusted by:
  - Search trend signal (rising trend → reduce discount slightly)
  - Margin floor constraint (client-set hard floor)
  - Days remaining in season (urgency amplifier)

Falls through to marketplace if margin floor is breached at max discount.
"""

from dataclasses import dataclass, field
import math

import pandas as pd

from config import STAGE3


@dataclass
class Stage3Result:
    action: str          # "markdown" | "marketplace" | "pass"
    recommended_discount_pct: float
    projected_clearance_days: float | None
    reason: str
    stub_warnings: list[str] = field(default_factory=list)


def evaluate(row: pd.Series, client: dict) -> Stage3Result:
    stub_warnings: list[str] = []

    if row.get("demand_elasticity") == -1.5:
        stub_warnings.append("demand_elasticity is default — lift projection is approximate")
    if row.get("competitor_price") is None:
        stub_warnings.append("competitor_price not set — pricing relative to market unverified")
    if row.get("bundle_candidates") == []:
        stub_warnings.append("bundle_candidates not evaluated")

    tier = row["urgency_tier"]
    margin_floor = client["markdown_margin_floor"]
    max_discount = client["markdown_max_discount"]

    # Base discount from urgency tier
    base_discount = STAGE3["discount_by_tier"].get(tier, max_discount)

    # Reduce discount if search trend is rising (item gaining organic interest)
    trend_dir = row.get("trend_direction", "flat")
    if trend_dir == "rising":
        base_discount = max(0.0, base_discount - STAGE3["trend_discount_adjustment"])

    # Amplify if season is almost over
    days_left = row.get("days_until_season_end", 365)
    if days_left < 14:
        base_discount = min(max_discount, base_discount + 0.10)
    elif days_left < 30:
        base_discount = min(max_discount, base_discount + 0.05)

    recommended_discount = min(base_discount, max_discount)

    # Check margin floor
    discounted_price = row["current_price"] * (1 - recommended_discount)
    if discounted_price > 0:
        margin_at_discount = (discounted_price - row["cost"]) / discounted_price
    else:
        margin_at_discount = 0.0

    clearance_days = _estimate_clearance_days(
        row["units_on_hand"],
        row.get("velocity_30d", 0.0),
        recommended_discount,
        row.get("demand_elasticity", -1.5),
    )

    if margin_at_discount >= margin_floor:
        return Stage3Result(
            action="markdown",
            recommended_discount_pct=round(recommended_discount * 100, 1),
            projected_clearance_days=clearance_days,
            reason=(
                f"Apply {recommended_discount:.0%} markdown "
                f"(urgency={tier}, trend={trend_dir}, {days_left}d to season end). "
                f"Margin after discount: {margin_at_discount:.0%}. "
                + (f" Est. clearance: {clearance_days:.0f}d." if clearance_days else "")
            ),
            stub_warnings=stub_warnings,
        )

    # Margin floor breached — route to marketplace (no floor constraint)
    return Stage3Result(
        action="marketplace",
        recommended_discount_pct=round(recommended_discount * 100, 1),
        projected_clearance_days=clearance_days,
        reason=(
            f"Margin at {recommended_discount:.0%} discount ({margin_at_discount:.0%}) "
            f"is below floor ({margin_floor:.0%}). Route to marketplace channel "
            "where margin floor does not apply."
        ),
        stub_warnings=stub_warnings,
    )


def _estimate_clearance_days(
    units: int,
    base_velocity: float,
    discount: float,
    elasticity: float,
) -> float | None:
    if base_velocity <= 0 or units <= 0:
        return None
    # Simple price-elasticity lift: %Δvelocity ≈ elasticity × %Δprice
    # price drops by `discount` fraction → %Δprice = -discount
    lift = 1 + (elasticity * (-discount))
    lift = max(lift, 0.1)  # floor at 10% of base velocity
    adjusted_velocity = base_velocity * lift
    return math.ceil(units / adjusted_velocity)

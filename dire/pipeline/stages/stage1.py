"""
Stage 1 — Should we intervene?

Returns hold if any of these are true:
  1. Positive velocity momentum (SKU is picking up, don't touch it)
  2. Not stagnant long enough per client threshold
  3. Sell-through is close enough to target (on track)
  4. Forecast confidence is too low to act reliably
  5. Urgency tier is green
Otherwise: intervene → proceed to Stage 2.
"""

from dataclasses import dataclass, field

import pandas as pd

from config import STAGE1


@dataclass
class Stage1Result:
    should_intervene: bool
    reason: str
    hold_signals: list[str] = field(default_factory=list)


def evaluate(row: pd.Series, client: dict) -> Stage1Result:
    holds: list[str] = []

    if row["urgency_tier"] == "green":
        holds.append("urgency tier is green")

    if row.get("velocity_change_rate", 0.0) > STAGE1["momentum_hold_threshold"]:
        holds.append(
            f"positive velocity momentum ({row['velocity_change_rate']:.0%} acceleration)"
        )

    if row["days_since_last_sale"] < client["intervention_days_stagnant"]:
        holds.append(
            f"stagnant only {row['days_since_last_sale']}d "
            f"(threshold: {client['intervention_days_stagnant']}d)"
        )

    expected = client["expected_sell_through"]
    if row["sell_through_rate"] >= expected * STAGE1["on_track_buffer"]:
        holds.append(
            f"sell-through {row['sell_through_rate']:.0%} is near target ({expected:.0%})"
        )

    # Confidence floor only blocks action on uncertain yellow/orange situations.
    # Red-tier SKUs (clearly dead) get routed regardless of confidence.
    if (
        row.get("forecast_confidence", 1.0) < STAGE1["confidence_hold_floor"]
        and row.get("urgency_tier") != "red"
    ):
        holds.append(
            f"forecast confidence {row['forecast_confidence']:.0%} is below floor — "
            "too uncertain to act"
        )

    if holds:
        return Stage1Result(
            should_intervene=False,
            reason="Hold: " + "; ".join(holds),
            hold_signals=holds,
        )

    return Stage1Result(
        should_intervene=True,
        reason=(
            f"Intervene: urgency={row['urgency_tier']}, "
            f"sell-through={row['sell_through_rate']:.0%} vs target {expected:.0%}, "
            f"stagnant {row['days_since_last_sale']}d"
        ),
    )

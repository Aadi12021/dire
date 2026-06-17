"""
Stage 4 — Sustainability Routing.

Decision order:
  1. Donate — preferred if esg_reporting_pressure or tax_deduction_eligible,
               units meet partner minimum, material is donateable
  2. Recycle — if material is recyclable and units meet threshold
  3. Liquidate — fallback; compare liquidation return to holding cost
"""

from dataclasses import dataclass, field

import pandas as pd

from config import STAGE4

_DONATEABLE_MATERIALS = {"textile", "clothing", "apparel", "toys", "books", "unknown"}
_RECYCLABLE_MATERIALS = {"electronics", "plastic", "metal", "cardboard", "unknown"}


@dataclass
class Stage4Result:
    action: str          # "donate" | "recycle" | "liquidate"
    partner: str | None
    reason: str
    stub_warnings: list[str] = field(default_factory=list)


def evaluate(row: pd.Series, client: dict) -> Stage4Result:
    stub_warnings: list[str] = []

    materials = row.get("material_composition", ["unknown"])
    if materials == ["unknown"]:
        stub_warnings.append("material_composition not set — routing based on category default")
        materials = _infer_materials_from_category(row.get("category", ""))

    partner = row.get("sustainability_partner")
    if partner is None:
        stub_warnings.append("sustainability_partner not set — partner registry not consulted")

    tax_eligible = row.get("tax_deduction_eligible", False)
    esg_priority = row.get("esg_reporting_pressure", False) or client.get("esg_priority", False)
    units = row.get("units_on_hand", 0)

    # ── Donate path ───────────────────────────────────────────────────────────
    can_donate = any(m in _DONATEABLE_MATERIALS for m in materials)
    if can_donate and units >= STAGE4["min_donate_units"] and (esg_priority or tax_eligible):
        reason = (
            f"Donate {units} units"
            + (" — ESG reporting priority." if esg_priority else "")
            + (" Tax deduction eligible." if tax_eligible else "")
        )
        if partner:
            reason += f" Matched partner: {partner}."
        return Stage4Result(action="donate", partner=partner, reason=reason,
                            stub_warnings=stub_warnings)

    # Donate without ESG/tax trigger if units are large and partner is matched
    if can_donate and units >= STAGE4["min_donate_units"] and partner:
        return Stage4Result(
            action="donate",
            partner=partner,
            reason=f"Donate {units} units to matched partner ({partner}).",
            stub_warnings=stub_warnings,
        )

    # ── Recycle path ──────────────────────────────────────────────────────────
    can_recycle = any(m in _RECYCLABLE_MATERIALS for m in materials)
    if can_recycle and units >= STAGE4["min_recycle_units"]:
        return Stage4Result(
            action="recycle",
            partner=None,
            reason=f"Route {units} units to materials recycling program.",
            stub_warnings=stub_warnings,
        )

    # ── Liquidate fallback ────────────────────────────────────────────────────
    liquidation_value = units * row.get("cost", 0) * 0.20  # rough liquidation rate
    return Stage4Result(
        action="liquidate",
        partner=None,
        reason=(
            f"Liquidate {units} units (est. recovery ~${liquidation_value:,.0f} "
            "at ~20% of cost). Sustainability routing not viable at this quantity/material."
        ),
        stub_warnings=stub_warnings,
    )


def _infer_materials_from_category(category: str) -> list[str]:
    mapping = {
        "Clothing": ["textile"],
        "Apparel": ["textile"],
        "Electronics": ["electronics"],
        "Home Goods": ["unknown"],
        "Sports": ["unknown"],
        "Toys": ["toys"],
        "Food": ["unknown"],
        "Beauty": ["unknown"],
    }
    return mapping.get(category, ["unknown"])

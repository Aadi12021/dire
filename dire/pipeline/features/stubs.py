"""
Typed stub fields for data that has no source yet.

A StubField is present in every SKU row but marked unset until real data
arrives. Stage logic that reads an unset stub logs a warning and uses the
safe default rather than crashing.
"""

from dataclasses import dataclass, field
from typing import Any
import warnings


@dataclass
class StubField:
    name: str
    default: Any
    description: str
    _value: Any = field(default=None, init=False, repr=False)
    _is_set: bool = field(default=False, init=False, repr=False)

    def set(self, value: Any) -> None:
        self._value = value
        self._is_set = True

    def get(self) -> Any:
        if not self._is_set:
            warnings.warn(
                f"Stub field '{self.name}' has no real data — using default "
                f"({self.default!r}). {self.description}",
                stacklevel=2,
            )
            return self.default
        return self._value

    @property
    def is_set(self) -> bool:
        return self._is_set


# ── Stub field definitions ────────────────────────────────────────────────────

STUB_DEFINITIONS: dict[str, dict] = {
    # Discount history
    "discount_history_ever": {
        "default": False,
        "description": "Has this SKU ever been marked down? Source: ERP/POS history.",
    },
    "discount_history_max_pct": {
        "default": 0.0,
        "description": "Maximum markdown depth applied historically (0–1). Source: ERP.",
    },
    "discount_history_lift": {
        "default": 1.0,
        "description": "Observed sell-through lift at max discount (multiplier). Source: ERP.",
    },
    # Demand elasticity
    "demand_elasticity": {
        "default": -1.5,
        "description": "Price elasticity of demand estimate. Source: pricing model / A-B tests.",
    },
    # Product attributes
    "perishability_days": {
        "default": None,
        "description": "Shelf life in days. None = not perishable. Source: product master.",
    },
    "material_composition": {
        "default": ["unknown"],
        "description": "List of materials (recyclable, textile, electronics, etc.). Source: product master.",
    },
    # Pricing signals
    "competitor_price": {
        "default": None,
        "description": "Lowest competitor price for equivalent SKU. Source: pricing API.",
    },
    "marketplace_sell_through_rate": {
        "default": None,
        "description": "Current sell-through on secondary marketplaces. Source: marketplace API.",
    },
    # Redistribution logistics
    "transport_cost_per_unit": {
        "default": None,
        "description": "Freight cost per unit for inter-store transfer. Source: logistics API.",
    },
    "transit_time_days": {
        "default": None,
        "description": "Transit days between origin and destination store. Source: logistics API.",
    },
    # Sustainability
    "tax_deduction_eligible": {
        "default": False,
        "description": "Whether donation qualifies for tax deduction. Source: accounting / legal.",
    },
    "bundle_candidates": {
        "default": [],
        "description": "SKU IDs that could be bundled with this one. Source: merchandising rules.",
    },
}


def make_stub_row() -> dict[str, Any]:
    """Return a dict of all stub fields set to their safe defaults."""
    return {name: defn["default"] for name, defn in STUB_DEFINITIONS.items()}


def unset_stubs(row: dict) -> list[str]:
    """Return the names of stub fields that are still at their default value."""
    return [
        name
        for name, defn in STUB_DEFINITIONS.items()
        if name in row and row[name] == defn["default"]
    ]

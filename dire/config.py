# ── Cost / price derivation (placeholders until real cost data is available) ──
COST_MULTIPLIER = 0.45
ORIGINAL_PRICE_MULTIPLIER = 1.3

# ── Stage thresholds ──────────────────────────────────────────────────────────

STAGE1 = {
    "momentum_hold_threshold": 0.10,   # velocity_change_rate > this → hold (positive momentum)
    "confidence_hold_floor": 0.35,     # forecast_confidence < this → hold (too uncertain)
    "on_track_buffer": 0.90,           # sell_through >= expected * this → hold (nearly on track)
}

STAGE2 = {
    "min_demand_differential": 0.25,   # destination velocity must be this much higher (fraction)
    "min_transfer_units": 10,          # don't move fewer than this many units
    "destination_capacity_floor": 0.3, # destination sell_through must be > this (it has real demand)
}

STAGE3 = {
    "markdown_max_discount": 0.40,
    "markdown_margin_floor": 0.10,
    # Discount by urgency tier
    "discount_by_tier": {
        "yellow": 0.10,
        "orange": 0.25,
        "red":    0.40,
    },
    "trend_discount_adjustment": 0.05,  # reduce discount this much if trend is rising
}

STAGE4 = {
    "min_donate_units": 10,
    "min_recycle_units": 1,
    "liquidation_margin_floor": 0.0,   # liquidate if any margin remains
}

SUSTAINABILITY_SCORE = {
    "hold":         100,
    "redistribute":  85,
    "markdown":      75,
    "marketplace":   70,
    "donate":        80,
    "recycle":       40,
    "liquidate":     30,
}

# ── Season calendar ───────────────────────────────────────────────────────────
# Maps category → (peak_start_month, peak_end_month)
# Used to compute days_until_season_end relative to dataset max date.

CATEGORY_SEASONS: dict[str, tuple[int, int]] = {
    "Clothing":      (3, 8),    # spring/summer: Mar–Aug
    "Apparel":       (3, 8),
    "Electronics":   (10, 12),  # holiday: Oct–Dec
    "Home Goods":    (3, 8),
    "Sports":        (3, 8),
    "Toys":          (10, 12),
    "Food":          (1, 12),   # year-round
    "Beauty":        (1, 12),
}
DEFAULT_SEASON_END_MONTH = 12   # December fallback for unknown categories

# ── Google Trends ─────────────────────────────────────────────────────────────
TRENDS_CACHE_HOURS = 24
TRENDS_CACHE_PATH = "data/.trends_cache.json"

# Maps Kaggle category names → Google Trends search keywords
CATEGORY_TREND_KEYWORDS: dict[str, str] = {
    "Clothing":    "clothing",
    "Apparel":     "apparel",
    "Electronics": "electronics",
    "Home Goods":  "home goods",
    "Sports":      "sports equipment",
    "Toys":        "toys",
    "Food":        "grocery",
    "Beauty":      "beauty products",
}

# ── Client profiles ───────────────────────────────────────────────────────────
# Each client overrides specific thresholds. Runner picks client by id.

CLIENTS: dict[str, dict] = {
    "default": {
        "intervention_days_stagnant": 45,
        "expected_sell_through":      0.70,
        "markdown_margin_floor":      0.10,
        "markdown_max_discount":      0.40,
        "min_transfer_units":         10,
        "esg_priority":               False,
    },
}


def get_client(client_id: str = "default") -> dict:
    if client_id not in CLIENTS:
        raise ValueError(f"Unknown client {client_id!r}. Available: {list(CLIENTS)}")
    return {**CLIENTS["default"], **CLIENTS[client_id]}

import anthropic


def explain_sku(row: dict, api_key: str) -> str:
    """Generate a 2-3 sentence explanation for a SKU recommendation via Claude."""
    client = anthropic.Anthropic(api_key=api_key)

    sell_through = row.get("sell_through_rate") or 0.0
    velocity_change = row.get("velocity_change_rate") or 0.0
    discount_line = (
        f"\nRecommended discount: {row['recommended_discount_pct']}%"
        if row.get("recommended_discount_pct") else ""
    )
    reroute_line = (
        f"\nReroute to: {row['redistribution_destination']}"
        if row.get("redistribution_destination") else ""
    )

    prompt = (
        "You are an inventory analyst at a retail chain. "
        "Write 2-3 concise sentences explaining why this SKU received its recommendation "
        "and what the store manager should do next. "
        "Be specific — cite the numbers. No markdown, no bullet points, no preamble.\n\n"
        f"SKU: {row.get('sku_id', 'unknown')}\n"
        f"Category: {row.get('category', 'unknown')}\n"
        f"Urgency tier: {row.get('urgency_tier', 'unknown')}\n"
        f"Sell-through rate: {sell_through:.0%}\n"
        f"Days since last sale: {row.get('days_since_last_sale', 'unknown')}\n"
        f"30-day sales velocity: {row.get('velocity_30d', 0):.2f} units/day\n"
        f"Velocity trend: {velocity_change:+.0%}\n"
        f"Recommendation: {row.get('recommendation', 'unknown')}\n"
        f"Action detail: {row.get('recommendation_detail', '')}"
        f"{discount_line}{reroute_line}"
    )

    message = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )
    return next(b.text for b in message.content if b.type == "text")

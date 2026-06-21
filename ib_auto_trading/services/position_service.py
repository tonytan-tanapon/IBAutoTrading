from __future__ import annotations

from typing import Any

from ..ib_client import IBClient


def position_snapshots(
    client: IBClient,
    *,
    ensure_market_data: bool = False,
) -> list[dict[str, Any]]:
    with client.lock:
        positions = [dict(position) for position in client.positions.values()]

    for position in positions:
        symbol = position["symbol"]
        market = client.get_market_data(symbol)
        if market is None and ensure_market_data:
            market = client.subscribe_market_data(symbol)
        if not market:
            continue

        market_price = market.get("last") or market.get("close")
        if market_price is None:
            continue

        market_value = market_price * position["quantity"]
        cost_value = position["average_cost"] * position["quantity"]
        position["market_price"] = market_price
        position["market_value"] = market_value
        position["unrealized_pnl"] = market_value - cost_value

    return positions

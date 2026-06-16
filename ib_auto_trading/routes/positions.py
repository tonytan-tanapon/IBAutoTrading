from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ..dependencies import get_ib_client
from ..ib_client import IBClient


router = APIRouter(prefix="/api/positions", tags=["positions"])


@router.get("")
def get_positions(
    refresh: bool = False,
    client: IBClient = Depends(get_ib_client),
) -> dict[str, Any]:
    if not client.is_ready():
        return {"connected": False, "positions": []}

    if refresh:
        client.request_positions()

    result = []
    with client.lock:
        positions = [dict(position) for position in client.positions.values()]

    for position in positions:
        symbol = position["symbol"]
        market = client.get_market_data(symbol)
        if market is None:
            try:
                market = client.subscribe_market_data(symbol)
            except (RuntimeError, ValueError) as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        market_price = market.get("last") or market.get("close")
        if market_price is not None:
            market_value = market_price * position["quantity"]
            cost_value = position["average_cost"] * position["quantity"]
            position["market_price"] = market_price
            position["market_value"] = market_value
            position["unrealized_pnl"] = market_value - cost_value

        result.append(position)

    return {"connected": True, "positions": result}

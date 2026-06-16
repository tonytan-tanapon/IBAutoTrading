from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..dependencies import get_ib_client
from ..ib_client import IBClient


router = APIRouter(prefix="/api/market-data", tags=["market-data"])


class MarketSubscription(BaseModel):
    symbol: str = Field(min_length=1, max_length=12)


@router.get("")
def list_market_data(
    client: IBClient = Depends(get_ib_client),
) -> dict[str, Any]:
    return {
        "connected": client.is_ready(),
        "items": client.get_market_data(),
    }


@router.post("/subscribe")
def subscribe_market_data(
    request: MarketSubscription,
    client: IBClient = Depends(get_ib_client),
) -> dict[str, Any]:
    try:
        data = client.subscribe_market_data(request.symbol)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"message": f"Subscribed to {request.symbol.upper()}", "data": data}


@router.post("/unsubscribe")
def unsubscribe_market_data(
    request: MarketSubscription,
    client: IBClient = Depends(get_ib_client),
) -> dict[str, Any]:
    removed = client.unsubscribe_market_data(request.symbol)
    return {
        "message": (
            f"Unsubscribed from {request.symbol.upper()}"
            if removed
            else f"{request.symbol.upper()} was not subscribed"
        )
    }

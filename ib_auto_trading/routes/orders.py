import time
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator

from ..dependencies import get_ib_client
from ..ib_client import IBClient
from ..order_previews import OrderPreview, preview_store
from ..risk import risk_settings


router = APIRouter(prefix="/api/orders", tags=["orders"])


class OrderRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=12)
    action: Literal["BUY", "SELL"]
    quantity: int = Field(gt=0)
    order_type: Literal["MKT", "LMT"]
    limit_price: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_limit_price(self) -> "OrderRequest":
        if self.order_type == "LMT" and self.limit_price is None:
            raise ValueError("limit_price is required for LMT orders")
        return self


class SubmitRequest(BaseModel):
    preview_id: str = Field(min_length=1)


def _estimated_price(request: OrderRequest, client: IBClient) -> float:
    if request.order_type == "LMT":
        return float(request.limit_price)

    market = client.get_market_data(request.symbol)
    if not market:
        raise HTTPException(
            status_code=400,
            detail="Subscribe to market data before previewing a market order",
        )

    price = market.get("ask") if request.action == "BUY" else market.get("bid")
    price = price or market.get("last") or market.get("close")
    if price is None:
        raise HTTPException(
            status_code=400,
            detail="No market price is available for this symbol",
        )
    return float(price)


def _validate_risk(
    request: OrderRequest,
    estimated_value: float,
    client: IBClient,
) -> None:
    if not client.is_ready():
        raise HTTPException(status_code=400, detail="TWS is not connected")
    if risk_settings.kill_switch:
        raise HTTPException(status_code=403, detail="Risk kill switch is enabled")
    if risk_settings.paper_only and not client.is_paper_account():
        raise HTTPException(
            status_code=403,
            detail="Orders are allowed only on an IBKR Paper Account (DU...)",
        )
    if request.quantity > risk_settings.max_quantity:
        raise HTTPException(
            status_code=400,
            detail=f"Quantity exceeds the limit of {risk_settings.max_quantity}",
        )
    if estimated_value > risk_settings.max_order_value:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Estimated value exceeds the limit of "
                f"{risk_settings.max_order_value:.2f}"
            ),
        )


@router.get("")
def get_orders(
    client: IBClient = Depends(get_ib_client),
) -> dict[str, object]:
    return {"connected": client.is_ready(), "orders": client.get_orders()}


@router.post("/preview")
def preview_order(
    request: OrderRequest,
    client: IBClient = Depends(get_ib_client),
) -> dict[str, object]:
    symbol = request.symbol.strip().upper()
    request.symbol = symbol
    estimated_price = _estimated_price(request, client)
    estimated_value = estimated_price * request.quantity
    _validate_risk(request, estimated_value, client)

    preview = OrderPreview(
        symbol=symbol,
        action=request.action,
        quantity=request.quantity,
        order_type=request.order_type,
        limit_price=request.limit_price,
        estimated_price=estimated_price,
        estimated_value=estimated_value,
        expires_at=time.time() + 300,
    )
    preview_id = preview_store.create(preview)
    return {"preview_id": preview_id, "preview": preview.to_dict()}


@router.post("/submit")
def submit_order(
    request: SubmitRequest,
    client: IBClient = Depends(get_ib_client),
) -> dict[str, object]:
    try:
        preview = preview_store.pop_valid(request.preview_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    order_request = OrderRequest(
        symbol=preview.symbol,
        action=preview.action,
        quantity=preview.quantity,
        order_type=preview.order_type,
        limit_price=preview.limit_price,
    )
    _validate_risk(order_request, preview.estimated_value, client)

    try:
        order_id = client.submit_order(
            symbol=preview.symbol,
            action=preview.action,
            quantity=preview.quantity,
            order_type=preview.order_type,
            limit_price=preview.limit_price,
        )
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"message": "Paper order submitted", "order_id": order_id}


@router.post("/{order_id}/cancel")
def cancel_order(
    order_id: int,
    client: IBClient = Depends(get_ib_client),
) -> dict[str, object]:
    try:
        client.cancel_order(order_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"message": f"Cancel requested for order {order_id}"}

from __future__ import annotations

import time
from typing import Protocol

from ..ib_client import IBClient
from ..order_previews import OrderPreview, preview_store
from ..risk import RiskSettings, risk_settings


class OrderLike(Protocol):
    symbol: str
    action: str
    quantity: int
    order_type: str
    limit_price: float | None


def estimated_price(request: OrderLike, client: IBClient) -> float:
    if request.order_type == "LMT":
        return float(request.limit_price)

    market = client.get_market_data(request.symbol)
    if not market:
        raise ValueError("Subscribe to market data before previewing a market order")

    price = market.get("ask") if request.action == "BUY" else market.get("bid")
    price = price or market.get("last") or market.get("close")
    if price is None:
        raise ValueError("No market price is available for this symbol")
    return float(price)


def validate_risk(
    request: OrderLike,
    estimated_value: float,
    client: IBClient,
    settings: RiskSettings = risk_settings,
) -> None:
    if not client.is_ready():
        raise ValueError("TWS is not connected")
    if settings.kill_switch:
        raise PermissionError("Risk kill switch is enabled")
    if settings.paper_only and not client.is_paper_account():
        raise PermissionError("Orders are allowed only on an IBKR Paper Account (DU...)")
    if request.quantity > settings.max_quantity:
        raise ValueError(f"Quantity exceeds the limit of {settings.max_quantity}")
    if estimated_value > settings.max_order_value:
        raise ValueError(
            f"Estimated value exceeds the limit of {settings.max_order_value:.2f}"
        )


def create_order_preview(request: OrderLike, client: IBClient) -> tuple[str, OrderPreview]:
    request.symbol = request.symbol.strip().upper()
    price = estimated_price(request, client)
    estimated_value = price * request.quantity
    validate_risk(request, estimated_value, client)

    preview = OrderPreview(
        symbol=request.symbol,
        action=request.action,
        quantity=request.quantity,
        order_type=request.order_type,
        limit_price=request.limit_price,
        estimated_price=price,
        estimated_value=estimated_value,
        expires_at=time.time() + 300,
    )
    return preview_store.create(preview), preview


def submit_preview_order(preview_id: str, client: IBClient) -> int:
    preview = preview_store.pop_valid(preview_id)
    validate_risk(preview, preview.estimated_value, client)
    return client.submit_order(
        symbol=preview.symbol,
        action=preview.action,
        quantity=preview.quantity,
        order_type=preview.order_type,
        limit_price=preview.limit_price,
    )

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator

from ..dependencies import get_ib_client
from ..ib_client import IBClient
from ..services.order_service import create_order_preview, submit_preview_order


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
    try:
        preview_id, preview = create_order_preview(request, client)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"preview_id": preview_id, "preview": preview.to_dict()}


@router.post("/submit")
def submit_order(
    request: SubmitRequest,
    client: IBClient = Depends(get_ib_client),
) -> dict[str, object]:
    try:
        order_id = submit_preview_order(request.preview_id, client)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
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

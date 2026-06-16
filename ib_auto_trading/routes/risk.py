from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..risk import risk_settings


router = APIRouter(prefix="/api/risk", tags=["risk"])


class RiskUpdate(BaseModel):
    max_quantity: int = Field(ge=1, le=10_000)
    max_order_value: float = Field(gt=0)
    kill_switch: bool


@router.get("")
def get_risk_settings() -> dict[str, bool | int | float]:
    return risk_settings.to_dict()


@router.put("")
def update_risk_settings(
    request: RiskUpdate,
) -> dict[str, bool | int | float]:
    risk_settings.max_quantity = request.max_quantity
    risk_settings.max_order_value = request.max_order_value
    risk_settings.kill_switch = request.kill_switch
    return risk_settings.to_dict()

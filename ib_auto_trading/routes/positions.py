from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ..dependencies import get_ib_client
from ..ib_client import IBClient
from ..realtime import realtime_broadcaster
from ..services.position_service import position_snapshots


router = APIRouter(prefix="/api/positions", tags=["positions"])


@router.get("")
def get_positions(
    refresh: bool = False,
    client: IBClient = Depends(get_ib_client),
) -> dict[str, Any]:
    realtime_broadcaster.log(
        "Loading positions with TWS refresh" if refresh else "Loading positions"
    )
    if not client.is_ready():
        realtime_broadcaster.log("Positions skipped: TWS is not connected")
        return {"connected": False, "positions": []}

    if refresh:
        client.request_positions()

    try:
        result = position_snapshots(client, ensure_market_data=True)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    realtime_broadcaster.log(f"Loaded {len(result)} positions")
    return {"connected": True, "positions": result}

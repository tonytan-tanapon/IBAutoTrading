from fastapi import APIRouter, Depends

from ..dependencies import get_ib_client, get_strategy_runner
from ..ib_client import IBClient
from ..strategy_runner import StrategyRunner


router = APIRouter(prefix="/api", tags=["connection"])


@router.get("/status")
def get_status(
    client: IBClient = Depends(get_ib_client),
) -> dict[str, bool | str | None]:
    return {
        "server": "running",
        "connected": client.is_ready(),
        "error": client.last_error,
    }


@router.post("/connect")
def connect_tws(
    client: IBClient = Depends(get_ib_client),
) -> dict[str, bool | str | None]:
    if client.is_ready():
        return {
            "connected": True,
            "message": "TWS is already connected",
            "error": None,
        }

    connected = client.connect_to_tws()
    return {
        "connected": connected,
        "message": "Connected to TWS" if connected else "Could not connect to TWS",
        "error": client.last_error,
    }


@router.post("/disconnect")
def disconnect_tws(
    client: IBClient = Depends(get_ib_client),
    runner: StrategyRunner = Depends(get_strategy_runner),
) -> dict[str, bool | str | None]:
    runner.stop()
    client.disconnect_from_tws()
    return {
        "connected": False,
        "message": "Disconnected from TWS",
        "error": None,
    }


@router.post("/disconnect-all")
def disconnect_all(
    client: IBClient = Depends(get_ib_client),
    runner: StrategyRunner = Depends(get_strategy_runner),
) -> dict[str, bool | str | None]:
    runner.stop()
    client.disconnect_from_tws()
    return {
        "connected": False,
        "message": (
            "Stopped strategy, cancelled data subscriptions, "
            "and disconnected this app from TWS"
        ),
        "error": None,
    }

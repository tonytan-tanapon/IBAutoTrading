from datetime import timedelta
from typing import Any, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator

from ..dependencies import get_ib_client, get_strategy_runner
from ..historical_signals import (
    completed_bars,
    previous_4h_range_history,
    sma_signal_history,
)
from ..ib_client import IBClient
from ..strategy_runner import StrategyRunner


router = APIRouter(prefix="/api/strategy", tags=["strategy"])


class StrategyConfigRequest(BaseModel):
    strategy_type: Literal["SMA", "PREVIOUS_4H_RANGE"] = "SMA"
    symbol: str = Field(min_length=1, max_length=12)
    short_window: int = Field(ge=1, le=500)
    long_window: int = Field(ge=2, le=1000)
    interval_seconds: int = Field(ge=60, le=86_400)

    @model_validator(mode="after")
    def validate_windows(self) -> "StrategyConfigRequest":
        if self.long_window <= self.short_window:
            raise ValueError("long_window must be greater than short_window")
        return self


class HistoricalSignalsRequest(BaseModel):
    strategy_type: Literal["SMA", "PREVIOUS_4H_RANGE"] = "SMA"
    symbol: str = Field(min_length=1, max_length=12)
    short_window: int = Field(default=5, ge=1, le=500)
    long_window: int = Field(default=20, ge=2, le=1000)
    limit: int = Field(default=200, ge=1, le=1000)

    @model_validator(mode="after")
    def validate_windows(self) -> "HistoricalSignalsRequest":
        if self.long_window <= self.short_window:
            raise ValueError("long_window must be greater than short_window")
        return self


@router.get("/status")
def get_strategy_status(
    runner: StrategyRunner = Depends(get_strategy_runner),
) -> dict[str, Any]:
    return runner.status()


@router.put("/config")
def configure_strategy(
    request: StrategyConfigRequest,
    runner: StrategyRunner = Depends(get_strategy_runner),
) -> dict[str, Any]:
    try:
        runner.configure(
            symbol=request.symbol,
            short_window=request.short_window,
            long_window=request.long_window,
            interval_seconds=request.interval_seconds,
            strategy_type=request.strategy_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return runner.status()


@router.post("/start")
def start_strategy(
    runner: StrategyRunner = Depends(get_strategy_runner),
) -> dict[str, Any]:
    try:
        runner.start()
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return runner.status()


@router.post("/stop")
def stop_strategy(
    runner: StrategyRunner = Depends(get_strategy_runner),
) -> dict[str, Any]:
    runner.stop()
    return runner.status()


@router.post("/check")
def check_strategy(
    background_tasks: BackgroundTasks,
    runner: StrategyRunner = Depends(get_strategy_runner),
) -> dict[str, Any]:
    if runner.status()["running_check"]:
        raise HTTPException(status_code=409, detail="A strategy check is already running")
    background_tasks.add_task(_run_check, runner)
    return {"message": "Strategy check started"}


@router.post("/history")
def get_historical_signals(
    request: HistoricalSignalsRequest,
    client: IBClient = Depends(get_ib_client),
) -> dict[str, Any]:
    if not client.is_ready():
        raise HTTPException(status_code=400, detail="Connect to TWS first")

    try:
        if request.strategy_type == "PREVIOUS_4H_RANGE":
            bars = client.request_historical_bars(
                request.symbol,
                duration="30 D",
                bar_size="4 hours",
            )
            signal_bars = completed_bars(bars, timedelta(hours=4))
            rows = previous_4h_range_history(signal_bars)
        else:
            bars = client.request_historical_bars(
                request.symbol,
                duration="2 D",
                bar_size="1 min",
            )
            signal_bars = completed_bars(bars, timedelta(minutes=1))
            rows = sma_signal_history(
                signal_bars,
                request.short_window,
                request.long_window,
            )
    except (RuntimeError, TimeoutError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "strategy_type": request.strategy_type,
        "symbol": request.symbol.strip().upper(),
        "bar_count": len(bars),
        "completed_bar_count": len(signal_bars),
        "rows": rows[-request.limit :],
    }


def _run_check(runner: StrategyRunner) -> None:
    try:
        runner.check_now()
    except (RuntimeError, TimeoutError, ValueError):
        pass

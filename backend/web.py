import traceback
from pathlib import Path
from threading import Lock, Thread

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import (
    DRY_RUN_ORDERS,
    STRATEGY_NAME,
    UNDERLYING_ASSET_TYPE,
    UNDERLYING_SYMBOL,
)
from .trading_engine import TradingEngine


app = FastAPI(title="IB Auto Trading Dashboard")
frontend_dir = Path(__file__).resolve().parents[1] / "frontend"
app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

engine = TradingEngine()
engine_lock = Lock()
engine_thread: Thread | None = None
engine_error: str | None = None


def run_engine():
    global engine_error

    try:
        engine_error = None
        engine.start()
        engine.load_initial_state()
        engine.subscribe_market_data(
            UNDERLYING_SYMBOL,
            asset_type=UNDERLYING_ASSET_TYPE,
        )
        engine.run_forever()

        if not engine.ib.isConnected():
            engine_error = "TWS connection closed"
    except Exception as exc:
        engine_error = f"{type(exc).__name__}: {exc}"
        print(f"Engine error: {engine_error}")
        traceback.print_exc()
    finally:
        engine.stop()


@app.get("/", response_class=FileResponse)
def dashboard():
    return frontend_dir / "index.html"


@app.get("/api/status")
def status():
    return {
        "web_server": "running",
        "symbol": UNDERLYING_SYMBOL,
        "strategy_name": STRATEGY_NAME,
        "dry_run_orders": DRY_RUN_ORDERS,
        "engine_running": engine.running,
        "tws_connected": engine.ib.isConnected(),
        "error": engine_error,
        "last_connection_close": engine.ib.last_connection_close,
        "recent_ib_errors": engine.ib.errors[-10:],
    }


@app.get("/api/dashboard")
def dashboard_data():
    snapshot = None
    snapshot_error = None

    if engine.running:
        try:
            snapshot = engine.get_strategy_snapshot()
        except Exception as exc:
            snapshot_error = str(exc)

    return {
        "symbol": UNDERLYING_SYMBOL,
        "market_data": dict(engine.ib.market_data),
        "account_summary": dict(engine.ib.account_summary),
        "positions": dict(engine.ib.positions),
        "orders": dict(engine.ib.orders),
        "strategy": snapshot,
        "strategy_error": snapshot_error,
        "historical_bar_count": len(engine.historical_data),
        "historical_data": list(engine.historical_data),
    }


@app.post("/api/engine/start")
def start_engine():
    global engine_thread

    with engine_lock:
        if engine_thread and engine_thread.is_alive():
            raise HTTPException(
                status_code=409,
                detail="Engine is already running",
            )

        engine_thread = Thread(target=run_engine, daemon=True)
        engine_thread.start()

    return {"message": "Engine is starting"}


@app.post("/api/engine/stop")
def stop_engine():
    engine.stop()
    return {"message": "Engine stopped"}

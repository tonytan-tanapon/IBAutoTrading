import traceback
from threading import Lock, Thread

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from .config import (
    UNDERLYING_ASSET_TYPE,
    UNDERLYING_SYMBOL,
)
from .trading_engine import TradingEngine


app = FastAPI(title="IB Auto Trading Dashboard")

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


@app.get("/", response_class=HTMLResponse)
def dashboard():
    return """
    <!DOCTYPE html>
    <html lang="th">
    <head>
        <meta charset="UTF-8">
        <title>IB Auto Trading</title>
    </head>
    <body>
        <h1>IB Auto Trading Dashboard</h1>

        <button onclick="startEngine()">Start Engine</button>
        <button onclick="stopEngine()">Stop Engine</button>

        <pre id="status">Loading...</pre>

        <h2>Trading Data</h2>
        <pre id="trading-data">Waiting for engine...</pre>

        <script>
            async function loadStatus() {
                const response = await fetch("/api/status");
                const data = await response.json();
                document.getElementById("status").textContent =
                    JSON.stringify(data, null, 2);
            }

            async function loadTradingData() {
                try {
                    const response = await fetch("/api/dashboard");
                    const data = await response.json();
                    document.getElementById("trading-data").textContent =
                        JSON.stringify(data, null, 2);
                } catch (error) {
                    document.getElementById("trading-data").textContent =
                        "Failed to load data: " + error;
                }
            }

            async function startEngine() {
                await fetch("/api/engine/start", { method: "POST" });
                await loadStatus();
            }

            async function stopEngine() {
                await fetch("/api/engine/stop", { method: "POST" });
                await loadStatus();
            }

            loadStatus();
            loadTradingData();

            setInterval(loadStatus, 2000);
            setInterval(loadTradingData, 2000);
        </script>
    </body>
    </html>
    """


@app.get("/api/status")
def status():
    return {
        "web_server": "running",
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
        "market_data": dict(engine.ib.market_data),
        "account_summary": dict(engine.ib.account_summary),
        "positions": dict(engine.ib.positions),
        "orders": dict(engine.ib.orders),
        "strategy": snapshot,
        "strategy_error": snapshot_error,
        "historical_bar_count": len(engine.historical_data),
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

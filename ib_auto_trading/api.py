from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from .routes import (
    account,
    connection,
    market_data,
    orders,
    positions,
    risk,
    strategy,
)
from .dependencies import ib_client, strategy_runner
from .realtime import realtime_websocket


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    strategy_runner.stop()
    ib_client.disconnect_from_tws()


app = FastAPI(title="IB Auto Trading API", lifespan=lifespan)
app.include_router(connection.router)
app.include_router(account.router)
app.include_router(positions.router)
app.include_router(market_data.router)
app.include_router(orders.router)
app.include_router(risk.router)
app.include_router(strategy.router)

frontend_directory = Path(__file__).resolve().parent.parent / "frontend"


@app.get("/")
def home() -> RedirectResponse:
    return RedirectResponse(url="/frontend/index.html")


@app.get("/orders")
def orders_page() -> RedirectResponse:
    return RedirectResponse(url="/frontend/index.html#orders")


@app.websocket("/ws/realtime")
async def websocket_realtime(websocket: WebSocket) -> None:
    await realtime_websocket(websocket, ib_client, strategy_runner)


app.mount(
    "/frontend",
    StaticFiles(directory=frontend_directory, html=True),
    name="frontend",
)

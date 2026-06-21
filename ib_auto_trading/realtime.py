from __future__ import annotations

import asyncio
import threading
import time
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from .ib_client import IBClient
from .risk import risk_settings
from .services.account_service import account_summary
from .services.position_service import position_snapshots
from .strategy_runner import StrategyRunner


class RealtimeBroadcaster:
    def __init__(self) -> None:
        self._condition = threading.Condition()
        self._version = 0
        self._log_id = 0
        self._logs: list[dict[str, Any]] = []

    @property
    def version(self) -> int:
        with self._condition:
            return self._version

    def notify(self) -> None:
        with self._condition:
            self._version += 1
            self._condition.notify_all()

    def log(self, message: str) -> None:
        with self._condition:
            self._log_id += 1
            self._logs.append(
                {
                    "id": self._log_id,
                    "timestamp": time.time(),
                    "message": message,
                }
            )
            self._logs = self._logs[-200:]
            self._version += 1
            self._condition.notify_all()

    def logs_snapshot(self) -> list[dict[str, Any]]:
        with self._condition:
            return [dict(item) for item in self._logs]

    def wait_for_update(self, last_version: int, timeout: float = 15) -> int:
        with self._condition:
            if self._version <= last_version:
                self._condition.wait_for(
                    lambda: self._version > last_version,
                    timeout=timeout,
                )
            return self._version


realtime_broadcaster = RealtimeBroadcaster()


def realtime_snapshot(
    client: IBClient,
    runner: StrategyRunner,
    version: int,
) -> dict[str, Any]:
    return {
        "type": "snapshot",
        "version": version,
        "timestamp": time.time(),
        "status": {
            "server": "running",
            "connected": client.is_ready(),
            "error": client.last_error,
        },
        "account": account_summary(client),
        "positions": position_snapshots(client),
        "market_data": client.get_market_data(),
        "orders": client.get_orders(),
        "risk": risk_settings.to_dict(),
        "strategy": runner.status(),
        "logs": realtime_broadcaster.logs_snapshot(),
    }


async def realtime_websocket(
    websocket: WebSocket,
    client: IBClient,
    runner: StrategyRunner,
) -> None:
    await websocket.accept()
    last_version = realtime_broadcaster.version
    await websocket.send_json(realtime_snapshot(client, runner, last_version))

    try:
        while True:
            next_version = await asyncio.to_thread(
                realtime_broadcaster.wait_for_update,
                last_version,
            )
            if next_version == last_version:
                await websocket.send_json({"type": "heartbeat", "version": next_version})
                continue

            await asyncio.sleep(0.1)
            last_version = realtime_broadcaster.version
            await websocket.send_json(realtime_snapshot(client, runner, last_version))
    except WebSocketDisconnect:
        return

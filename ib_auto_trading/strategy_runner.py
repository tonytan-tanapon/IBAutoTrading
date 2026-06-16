from __future__ import annotations

import threading
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from .ib_client import IBClient
from .strategies.previous_4h_range import previous_4h_range_signal
from .strategies.sma import sma_crossover


@dataclass
class StrategyConfig:
    strategy_type: str = "SMA"
    symbol: str = "SPY"
    short_window: int = 5
    long_window: int = 20
    bar_size: str = "1 min"
    duration: str = "2 D"
    interval_seconds: int = 60


class StrategyRunner:
    def __init__(self, client: IBClient) -> None:
        self.client = client
        self.config = StrategyConfig()
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.enabled = False
        self.running_check = False
        self.last_signal: str | None = None
        self.last_checked_at: str | None = None
        self.last_error: str | None = None
        self.last_close: float | None = None
        self.short_sma: float | None = None
        self.long_sma: float | None = None
        self.bar_count = 0
        self.previous_high: float | None = None
        self.previous_low: float | None = None
        self.range_size: float | None = None
        self.call_entry: float | None = None
        self.call_target: float | None = None
        self.call_stop: float | None = None
        self.put_entry: float | None = None
        self.put_target: float | None = None
        self.put_stop: float | None = None

    def configure(
        self,
        symbol: str,
        short_window: int,
        long_window: int,
        interval_seconds: int,
        strategy_type: str = "SMA",
    ) -> None:
        if not symbol.strip():
            raise ValueError("Symbol is required")
        strategy_type = strategy_type.strip().upper()
        if strategy_type not in {"SMA", "PREVIOUS_4H_RANGE"}:
            raise ValueError("Unsupported strategy type")
        if short_window <= 0 or long_window <= short_window:
            raise ValueError("Windows must satisfy 0 < short_window < long_window")
        if interval_seconds < 60:
            raise ValueError("Interval must be at least 60 seconds")

        with self.lock:
            self.config.strategy_type = strategy_type
            self.config.symbol = symbol.strip().upper()
            self.config.short_window = short_window
            self.config.long_window = long_window
            self.config.interval_seconds = interval_seconds
            self.last_signal = None
            self.last_error = None
            self._clear_results()

    def start(self) -> None:
        if not self.client.is_ready():
            raise RuntimeError("Connect to TWS before enabling the strategy")
        with self.lock:
            if self.enabled:
                return
            self.enabled = True
            self.stop_event.clear()
            self.thread = threading.Thread(target=self._run_loop, daemon=True)
            self.thread.start()

    def stop(self) -> None:
        with self.lock:
            self.enabled = False
            self.stop_event.set()
            thread = self.thread
            self.thread = None
        if thread and thread.is_alive():
            thread.join(timeout=2)

    def check_now(self) -> dict[str, Any]:
        with self.lock:
            if self.running_check:
                raise RuntimeError("A strategy check is already running")
            self.running_check = True
            config = StrategyConfig(**asdict(self.config))

        try:
            if config.strategy_type == "PREVIOUS_4H_RANGE":
                self._check_previous_4h_range(config)
            else:
                self._check_sma(config)
            checked_at = datetime.now().astimezone().isoformat(timespec="seconds")
            with self.lock:
                self.last_checked_at = checked_at
                self.last_error = None
        except (RuntimeError, TimeoutError, ValueError) as exc:
            with self.lock:
                self.last_checked_at = datetime.now().astimezone().isoformat(
                    timespec="seconds"
                )
                self.last_error = str(exc)
            raise
        finally:
            with self.lock:
                self.running_check = False

        return self.status()

    def status(self) -> dict[str, Any]:
        with self.lock:
            is_range = self.config.strategy_type == "PREVIOUS_4H_RANGE"
            return {
                "enabled": self.enabled,
                "running_check": self.running_check,
                "strategy_type": self.config.strategy_type,
                "name": (
                    "Previous 4H Range Breakout (signal only)"
                    if is_range
                    else "SMA Crossover (signal only)"
                ),
                "symbol": self.config.symbol,
                "short_window": self.config.short_window,
                "long_window": self.config.long_window,
                "bar_size": self.config.bar_size,
                "interval_seconds": self.config.interval_seconds,
                "last_signal": self.last_signal,
                "last_checked_at": self.last_checked_at,
                "last_close": self.last_close,
                "short_sma": self.short_sma,
                "long_sma": self.long_sma,
                "bar_count": self.bar_count,
                "previous_high": self.previous_high,
                "previous_low": self.previous_low,
                "range_size": self.range_size,
                "call_entry": self.call_entry,
                "call_target": self.call_target,
                "call_stop": self.call_stop,
                "put_entry": self.put_entry,
                "put_target": self.put_target,
                "put_stop": self.put_stop,
                "error": self.last_error,
                "message": (
                    "Signal-only mode. No orders are submitted automatically."
                ),
            }

    def _check_sma(self, config: StrategyConfig) -> None:
        bars = self.client.request_historical_bars(
            config.symbol,
            duration=config.duration,
            bar_size=config.bar_size,
        )
        closes = [bar["close"] for bar in bars]
        result = sma_crossover(
            closes,
            config.short_window,
            config.long_window,
        )
        with self.lock:
            self._clear_results()
            self.last_signal = result.signal
            self.last_close = closes[-1]
            self.short_sma = result.short_sma
            self.long_sma = result.long_sma
            self.bar_count = len(bars)

    def _check_previous_4h_range(self, config: StrategyConfig) -> None:
        bars = self.client.request_historical_bars(
            config.symbol,
            duration="10 D",
            bar_size="4 hours",
        )
        if len(bars) < 2:
            raise ValueError("At least two 4H bars are required")

        previous_bar = bars[-2]
        current_bar = bars[-1]
        market = self.client.get_market_data(config.symbol)
        if market is None:
            market = self.client.subscribe_market_data(config.symbol)
        price = (
            market.get("last")
            or market.get("close")
            or current_bar.get("close")
        )
        if price is None:
            raise ValueError("Current market price is not available")

        result = previous_4h_range_signal(
            price=float(price),
            previous_high=float(previous_bar["high"]),
            previous_low=float(previous_bar["low"]),
        )
        with self.lock:
            self._clear_results()
            self.last_signal = result.signal
            self.last_close = result.price
            self.bar_count = len(bars)
            self.previous_high = result.high
            self.previous_low = result.low
            self.range_size = result.range_size
            self.call_entry = result.call_entry
            self.call_target = result.call_target
            self.call_stop = result.call_stop
            self.put_entry = result.put_entry
            self.put_target = result.put_target
            self.put_stop = result.put_stop

    def _clear_results(self) -> None:
        self.last_close = None
        self.short_sma = None
        self.long_sma = None
        self.bar_count = 0
        self.previous_high = None
        self.previous_low = None
        self.range_size = None
        self.call_entry = None
        self.call_target = None
        self.call_stop = None
        self.put_entry = None
        self.put_target = None
        self.put_stop = None

    def _run_loop(self) -> None:
        while not self.stop_event.is_set():
            try:
                self.check_now()
            except (RuntimeError, TimeoutError, ValueError):
                pass

            with self.lock:
                interval = self.config.interval_seconds
            if self.stop_event.wait(interval):
                break

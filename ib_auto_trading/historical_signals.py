from datetime import datetime, timedelta, timezone
from typing import Any

from .strategies.previous_4h_range import previous_4h_range_signal
from .strategies.sma import sma_crossover


def completed_bars(
    bars: list[dict[str, Any]],
    bar_duration: timedelta,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    if not bars:
        return []

    latest_start = _parse_ib_bar_time(str(bars[-1]["time"]))
    if latest_start is None:
        return bars

    current_time = now or datetime.now()
    if current_time.tzinfo is not None:
        current_time = current_time.replace(tzinfo=None)

    if latest_start + bar_duration > current_time:
        return bars[:-1]
    return bars


def _parse_ib_bar_time(value: str) -> datetime | None:
    value = value.strip()

    if value.isdigit():
        try:
            return datetime.fromtimestamp(int(value), tz=timezone.utc).replace(
                tzinfo=None
            )
        except (OverflowError, OSError, ValueError):
            return None

    timestamp = value[:17]
    try:
        parsed = datetime.strptime(timestamp, "%Y%m%d %H:%M:%S")
    except ValueError:
        return None

    return parsed


def sma_signal_history(
    bars: list[dict[str, Any]],
    short_window: int,
    long_window: int,
) -> list[dict[str, Any]]:
    rows = []
    for index in range(long_window, len(bars)):
        window = bars[: index + 1]
        result = sma_crossover(
            [bar["close"] for bar in window],
            short_window,
            long_window,
        )
        bar = bars[index]
        rows.append(
            {
                "time": bar["time"],
                "price": bar["close"],
                "open": bar["open"],
                "high": bar["high"],
                "low": bar["low"],
                "close": bar["close"],
                "signal": result.signal,
                "short_sma": result.short_sma,
                "long_sma": result.long_sma,
            }
        )
    return rows


def previous_4h_range_history(
    bars: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    for index in range(1, len(bars)):
        previous_bar = bars[index - 1]
        current_bar = bars[index]
        result = previous_4h_range_signal(
            price=current_bar["close"],
            previous_high=previous_bar["high"],
            previous_low=previous_bar["low"],
        )
        rows.append(
            {
                "time": current_bar["time"],
                "price": current_bar["close"],
                "open": current_bar["open"],
                "high": current_bar["high"],
                "low": current_bar["low"],
                "close": current_bar["close"],
                "signal": result.signal,
                "previous_high": result.high,
                "previous_low": result.low,
                "call_entry": result.call_entry,
                "call_target": result.call_target,
                "call_stop": result.call_stop,
                "put_entry": result.put_entry,
                "put_target": result.put_target,
                "put_stop": result.put_stop,
            }
        )
    return rows

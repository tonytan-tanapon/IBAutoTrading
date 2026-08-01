from datetime import datetime, time, timedelta


TIME_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y%m%d %H:%M:%S",
    "%Y%m%d %H:%M",
)


def parse_timeframe_minutes(value: str):
    parts = value.strip().lower().split()

    if len(parts) != 2:
        raise ValueError(f"Invalid timeframe: {value}")

    amount = int(parts[0])
    unit = parts[1]

    if amount <= 0:
        raise ValueError("Timeframe amount must be greater than 0")

    if unit in ("s", "sec", "secs", "second", "seconds"):
        if amount % 60 != 0:
            raise ValueError(f"Timeframe must resolve to whole minutes: {value}")

        return amount // 60

    if unit in ("m", "min", "mins", "minute", "minutes"):
        return amount

    if unit in ("h", "hour", "hours"):
        return amount * 60

    if unit in ("d", "day", "days"):
        return amount * 24 * 60

    raise ValueError(f"Unsupported timeframe unit: {unit}")


def calculate_bars_per_timeframe(timeframe: str, bar_size: str):
    timeframe_minutes = parse_timeframe_minutes(timeframe)
    bar_minutes = parse_timeframe_minutes(bar_size)

    if timeframe_minutes % bar_minutes != 0:
        raise ValueError(
            f"{timeframe} is not evenly divisible by bar size {bar_size}"
        )

    return timeframe_minutes // bar_minutes


def parse_bar_datetime(value):
    if isinstance(value, datetime):
        return value

    text = str(value).strip()

    for time_format in TIME_FORMATS:
        try:
            return datetime.strptime(text, time_format)
        except ValueError:
            pass

    try:
        return datetime.fromisoformat(text)
    except ValueError as error:
        raise ValueError(f"Unsupported bar time format: {value}") from error


def parse_anchor_time(value: str):
    hour_text, minute_text = value.split(":", 1)
    return time(hour=int(hour_text), minute=int(minute_text))


def session_start_for_bar(bar_time, timeframe: str, anchor_time: str):
    bar_datetime = parse_bar_datetime(bar_time)
    anchor = parse_anchor_time(anchor_time)
    timeframe_minutes = parse_timeframe_minutes(timeframe)
    anchor_datetime = datetime.combine(bar_datetime.date(), anchor)

    if bar_datetime < anchor_datetime:
        anchor_datetime -= timedelta(days=1)

    elapsed_minutes = int((bar_datetime - anchor_datetime).total_seconds() // 60)
    session_index = elapsed_minutes // timeframe_minutes

    return anchor_datetime + timedelta(
        minutes=session_index * timeframe_minutes
    )


def completed_fixed_sessions(
    bars,
    timeframe: str,
    anchor_time: str,
    current_bar=None,
):
    if not bars:
        return []

    current_session_start = None

    if current_bar is not None:
        current_session_start = session_start_for_bar(
            current_bar["time"],
            timeframe,
            anchor_time,
        )

    session_bars = {}

    for bar in bars:
        session_start = session_start_for_bar(
            bar["time"],
            timeframe,
            anchor_time,
        )

        if session_start == current_session_start:
            continue

        session_bars.setdefault(session_start, []).append(bar)

    completed_sessions = []

    for session_start in sorted(session_bars):
        session = aggregate_ohlc(session_bars[session_start])
        session["session_start"] = session_start.isoformat(sep=" ")
        session["session_end"] = (
            session_start + timedelta(
                minutes=parse_timeframe_minutes(timeframe)
            )
        ).isoformat(sep=" ")
        session["bar_count"] = len(session_bars[session_start])
        completed_sessions.append(session)

    return completed_sessions


def calculate_ema(values, period: int):
    if period <= 0:
        raise ValueError("EMA period must be greater than 0")

    if not values:
        return []

    multiplier = 2 / (period + 1)
    ema_values = [values[0]]

    for value in values[1:]:
        previous_ema = ema_values[-1]
        ema_values.append((value - previous_ema) * multiplier + previous_ema)

    return ema_values


def aggregate_ohlc(bars):
    if not bars:
        raise ValueError("Cannot aggregate empty bars")

    return {
        "time": bars[-1]["time"],
        "open": float(bars[0]["open"]),
        "high": max(float(bar["high"]) for bar in bars),
        "low": min(float(bar["low"]) for bar in bars),
        "close": float(bars[-1]["close"]),
        "volume": sum(float(bar.get("volume", 0)) for bar in bars),
    }


def calculate_true_ranges(bars):
    true_ranges = []
    previous_close = None

    for bar in bars:
        high = float(bar["high"])
        low = float(bar["low"])

        if previous_close is None:
            true_range = high - low
        else:
            true_range = max(
                high - low,
                abs(high - previous_close),
                abs(low - previous_close),
            )

        true_ranges.append(true_range)
        previous_close = float(bar["close"])

    return true_ranges


def calculate_sma(values, period: int):
    if period <= 0:
        raise ValueError("SMA period must be greater than 0")

    sma_values = []

    for index in range(len(values)):
        start = max(0, index - period + 1)
        window = values[start:index + 1]
        sma_values.append(sum(window) / len(window))

    return sma_values


def calculate_rma(values, period: int):
    if period <= 0:
        raise ValueError("RMA period must be greater than 0")

    if not values:
        return []

    alpha = 1 / period
    rma_values = [values[0]]

    for value in values[1:]:
        previous_rma = rma_values[-1]
        rma_values.append(alpha * value + (1 - alpha) * previous_rma)

    return rma_values


def calculate_atr(bars, period: int, use_rma: bool = True):
    true_ranges = calculate_true_ranges(bars)

    if use_rma:
        return calculate_rma(true_ranges, period)

    return calculate_sma(true_ranges, period)


def calculate_atr_trailing_stop(
    bars,
    period: int = 10,
    multiplier: float = 1,
    use_rma: bool = True,
):
    atr_values = calculate_atr(bars, period, use_rma=use_rma)
    results = []
    previous_up = None
    previous_dn = None
    previous_trend = 1

    for index, bar in enumerate(bars):
        high = float(bar["high"])
        low = float(bar["low"])
        close = float(bar["close"])
        src = (high + low) / 2
        atr = atr_values[index]

        up = src - (multiplier * atr)
        dn = src + (multiplier * atr)

        up1 = previous_up if previous_up is not None else up
        dn1 = previous_dn if previous_dn is not None else dn

        previous_close = float(bars[index - 1]["close"]) if index > 0 else close

        if previous_close > up1:
            up = max(up, up1)

        if previous_close < dn1:
            dn = min(dn, dn1)

        trend = previous_trend

        if trend == -1 and close > dn1:
            trend = 1
        elif trend == 1 and close < up1:
            trend = -1

        results.append(
            {
                "time": bar["time"],
                "atr": atr,
                "up": up,
                "dn": dn,
                "trend": trend,
                "hl2_plus_atr": src + atr,
                "hl2_minus_atr": src - atr,
            }
        )

        previous_up = up
        previous_dn = dn
        previous_trend = trend

    return results

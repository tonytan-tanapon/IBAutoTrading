from dataclasses import dataclass
from statistics import fmean
from typing import Sequence


@dataclass(frozen=True)
class SmaResult:
    signal: str
    short_sma: float
    long_sma: float
    previous_short_sma: float
    previous_long_sma: float


def sma_crossover(
    closes: Sequence[float],
    short_window: int,
    long_window: int,
) -> SmaResult:
    if short_window <= 0 or long_window <= short_window:
        raise ValueError("Windows must satisfy 0 < short_window < long_window")
    if len(closes) < long_window + 1:
        raise ValueError(f"At least {long_window + 1} bars are required")

    previous_short = fmean(closes[-short_window - 1 : -1])
    current_short = fmean(closes[-short_window:])
    previous_long = fmean(closes[-long_window - 1 : -1])
    current_long = fmean(closes[-long_window:])

    signal = "HOLD"
    if previous_short <= previous_long and current_short > current_long:
        signal = "BUY"
    elif previous_short >= previous_long and current_short < current_long:
        signal = "SELL"

    return SmaResult(
        signal=signal,
        short_sma=current_short,
        long_sma=current_long,
        previous_short_sma=previous_short,
        previous_long_sma=previous_long,
    )

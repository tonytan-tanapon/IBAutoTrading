from ..config import EMA_FAST_PERIOD, EMA_SLOW_PERIOD, UNDERLYING_SYMBOL
from .base import BaseStrategy
from .indicators import calculate_ema


class EmaCrossStrategy(BaseStrategy):
    name = "ema_cross"

    def calculate(self, context):
        historical_data = context["historical_data"]
        minimum_bars = EMA_SLOW_PERIOD + 2
        values = {
            "fast_period": EMA_FAST_PERIOD,
            "slow_period": EMA_SLOW_PERIOD,
            "minimum_bars": minimum_bars,
        }

        if len(historical_data) < minimum_bars:
            return {
                "values": values,
                "conditions": {
                    "has_enough_bars": False,
                },
                "signal": None,
            }

        closes = [float(bar["close"]) for bar in historical_data]
        fast_ema = calculate_ema(closes, EMA_FAST_PERIOD)
        slow_ema = calculate_ema(closes, EMA_SLOW_PERIOD)

        previous_fast = fast_ema[-2]
        previous_slow = slow_ema[-2]
        current_fast = fast_ema[-1]
        current_slow = slow_ema[-1]

        crossed_up = previous_fast <= previous_slow and current_fast > current_slow
        crossed_down = previous_fast >= previous_slow and current_fast < current_slow

        values.update(
            {
                "previous_fast_ema": previous_fast,
                "previous_slow_ema": previous_slow,
                "current_fast_ema": current_fast,
                "current_slow_ema": current_slow,
                "fast_ema": fast_ema,
                "slow_ema": slow_ema,
            }
        )

        signal = None

        if crossed_up:
            signal = {
                "action": "BUY",
                "underlying": UNDERLYING_SYMBOL,
                "direction": "CALL",
                "reason": (
                    f"EMA cross up: fast {EMA_FAST_PERIOD} crossed above "
                    f"slow {EMA_SLOW_PERIOD}"
                ),
            }

        if crossed_down:
            signal = {
                "action": "SELL",
                "underlying": UNDERLYING_SYMBOL,
                "reason": (
                    f"EMA cross down: fast {EMA_FAST_PERIOD} crossed below "
                    f"slow {EMA_SLOW_PERIOD}"
                ),
            }

        return {
            "values": values,
            "conditions": {
                "has_enough_bars": True,
                "crossed_up": crossed_up,
                "crossed_down": crossed_down,
            },
            "signal": signal,
        }

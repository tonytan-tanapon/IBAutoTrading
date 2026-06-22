from ..config import (
    SIG_HL_ATR_MULTIPLIER,
    SIG_HL_ATR_PERIOD,
    SIG_HL_TF_BARS,
    UNDERLYING_SYMBOL,
)
from .base import BaseStrategy
from .indicators import aggregate_ohlc, calculate_atr_trailing_stop


class SigHL1mStrategy(BaseStrategy):
    name = "sig_hl_1m"

    def calculate(self, context):
        historical_data = context["historical_data"]
        minimum_bars = max(SIG_HL_TF_BARS * 2 + 2, SIG_HL_ATR_PERIOD + 2)
        values = {
            "tf_bars": SIG_HL_TF_BARS,
            "atr_period": SIG_HL_ATR_PERIOD,
            "atr_multiplier": SIG_HL_ATR_MULTIPLIER,
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

        latest_bar = historical_data[-1]
        previous_bar = historical_data[-2]
        completed_bars = historical_data[:-1]
        recent_completed_bars = completed_bars[-(SIG_HL_TF_BARS * 2):]

        prev_4h_2 = aggregate_ohlc(recent_completed_bars[:SIG_HL_TF_BARS])
        prev_4h_1 = aggregate_ohlc(recent_completed_bars[SIG_HL_TF_BARS:])

        prev_high_1 = prev_4h_1["high"]
        prev_low_1 = prev_4h_1["low"]
        prev_high_2 = prev_4h_2["high"]
        prev_low_2 = prev_4h_2["low"]

        hl_range = prev_high_1 - prev_low_1
        long_level = prev_high_1 + hl_range / 2
        short_level = prev_low_1 - hl_range / 2
        long_target = prev_high_1 + hl_range
        short_target = prev_low_1 - hl_range

        lower_high = prev_high_1 < prev_high_2
        higher_low = prev_low_1 > prev_low_2

        latest_high = float(latest_bar["high"])
        latest_low = float(latest_bar["low"])
        previous_high = float(previous_bar["high"])
        previous_low = float(previous_bar["low"])

        long_signal = lower_high and latest_high > long_level and latest_low < long_level
        short_signal = higher_low and latest_low < short_level and latest_high > short_level

        atr_trailing_stop = calculate_atr_trailing_stop(
            historical_data,
            period=SIG_HL_ATR_PERIOD,
            multiplier=SIG_HL_ATR_MULTIPLIER,
        )
        latest_atr_stop = atr_trailing_stop[-1]
        previous_atr_stop = atr_trailing_stop[-2]

        previous_call_atr = previous_atr_stop["up"]
        latest_call_atr = latest_atr_stop["up"]
        previous_put_atr = previous_atr_stop["dn"]
        latest_put_atr = latest_atr_stop["dn"]

        call_confirmation = previous_high < previous_call_atr and latest_high > latest_call_atr
        put_confirmation = previous_low > previous_put_atr and latest_low < latest_put_atr

        buy_call_signal = long_signal and call_confirmation
        buy_put_signal = short_signal and put_confirmation

        levels = {
            "prev_high_1": prev_high_1,
            "prev_low_1": prev_low_1,
            "prev_high_2": prev_high_2,
            "prev_low_2": prev_low_2,
            "hl_range": hl_range,
            "long_level": long_level,
            "long_target": long_target,
            "short_level": short_level,
            "short_target": short_target,
            "atr_up": latest_call_atr,
            "atr_dn": latest_put_atr,
        }
        values.update(
            {
                "prev_4h_1": prev_4h_1,
                "prev_4h_2": prev_4h_2,
                "levels": levels,
                "atr_trailing_stop": atr_trailing_stop,
                "latest_atr_stop": latest_atr_stop,
                "previous_atr_stop": previous_atr_stop,
            }
        )

        signal = None

        if buy_call_signal:
            signal = {
                "action": "BUY",
                "underlying": UNDERLYING_SYMBOL,
                "direction": "CALL",
                "reason": "SigHL long signal with ATR trailing stop call confirmation",
                "levels": levels,
            }

        if buy_put_signal:
            signal = {
                "action": "BUY",
                "underlying": UNDERLYING_SYMBOL,
                "direction": "PUT",
                "reason": "SigHL short signal with ATR trailing stop put confirmation",
                "levels": levels,
            }

        return {
            "values": values,
            "conditions": {
                "has_enough_bars": True,
                "lower_high": lower_high,
                "higher_low": higher_low,
                "long_signal": long_signal,
                "short_signal": short_signal,
                "call_confirmation": call_confirmation,
                "put_confirmation": put_confirmation,
                "buy_call_signal": buy_call_signal,
                "buy_put_signal": buy_put_signal,
            },
            "signal": signal,
        }

from ..config import SIG_HL_TF_BARS, UNDERLYING_SYMBOL
from .base import BaseStrategy
from .indicators import aggregate_ohlc


class SigHLStrategy(BaseStrategy):
    name = "sig_hl"

    def calculate(self, context):
        historical_data = context["historical_data"]
        minimum_bars = SIG_HL_TF_BARS * 2 + 3
        values = {
            "tf_bars": SIG_HL_TF_BARS,
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
        two_bars_ago = historical_data[-3]
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
        two_bars_ago_high = float(two_bars_ago["high"])
        two_bars_ago_low = float(two_bars_ago["low"])

        long_signal = lower_high and latest_high > long_level and latest_low < long_level
        short_signal = higher_low and latest_low < short_level and latest_high > short_level
        call_confirmation = previous_high < two_bars_ago_high and latest_high > previous_high
        put_confirmation = previous_low > two_bars_ago_low and latest_low < previous_low

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
        }
        values.update(
            {
                "prev_4h_1": prev_4h_1,
                "prev_4h_2": prev_4h_2,
                "levels": levels,
            }
        )

        signal = None

        if buy_call_signal:
            signal = {
                "action": "BUY",
                "underlying": UNDERLYING_SYMBOL,
                "direction": "CALL",
                "reason": "SigHL long signal with 5m call confirmation",
                "levels": levels,
            }

        if buy_put_signal:
            signal = {
                "action": "BUY",
                "underlying": UNDERLYING_SYMBOL,
                "direction": "PUT",
                "reason": "SigHL short signal with 5m put confirmation",
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

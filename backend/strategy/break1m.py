from dataclasses import dataclass
from enum import Enum

from ..config import (
    BREAK_1M_BOUNCE_DOLLARS,
    BREAK_1M_BREAKOUT_BUFFER,
    BREAK_1M_PULLBACK_DOLLARS,
    BREAK_1M_REWARD_RISK_RATIO,
    BREAK_1M_SESSION_ANCHOR,
    BREAK_1M_STOP_BUFFER,
    BREAK_1M_USE_CLOSE_CONFIRMATION,
    UNDERLYING_SYMBOL,
)
from .base import BaseStrategy
from .indicators import parse_anchor_time, parse_bar_datetime


class Bias(Enum):
    NEUTRAL = "neutral"
    UP = "up"
    DOWN = "down"


class SetupState(Enum):
    WAIT_DIRECTION = "wait_direction"
    UP_WAIT_PULLBACK = "up_wait_pullback"
    UP_WAIT_BOUNCE = "up_wait_bounce"
    DOWN_WAIT_BOUNCE = "down_wait_bounce"
    DOWN_WAIT_DROP = "down_wait_drop"


@dataclass
class MachineState:
    bias: Bias = Bias.NEUTRAL
    setup: SetupState = SetupState.WAIT_DIRECTION
    up_peak: float | None = None
    pullback_low: float | None = None
    down_trough: float | None = None
    bounce_high: float | None = None


class Break1MStrategy(BaseStrategy):
    name = "break1m"

    def calculate(self, context):
        historical_data = context.get("historical_data", [])
        values = self._base_values()

        session_bars = self._latest_session_bars(historical_data)
        if not session_bars:
            return self._result(values, {"has_opening_bar": False})

        opening_bar = session_bars[0]
        opening_high = float(opening_bar["high"])
        opening_low = float(opening_bar["low"])
        values.update({
            "opening_bar": opening_bar,
            "opening_high": opening_high,
            "opening_low": opening_low,
        })

        if len(session_bars) == 1:
            return self._result(values, {
                "has_opening_bar": True,
                "has_bars_after_open": False,
            })

        state = MachineState()
        latest_signal = None

        for index, bar in enumerate(session_bars[1:], start=1):
            signal = self._update(state, bar, opening_high, opening_low)
            if index == len(session_bars) - 1:
                latest_signal = signal

        values.update({
            "bias": state.bias.value,
            "state": state.setup.value,
            "up_peak": state.up_peak,
            "pullback_low": state.pullback_low,
            "down_trough": state.down_trough,
            "bounce_high": state.bounce_high,
        })
        if latest_signal:
            values["levels"] = latest_signal["levels"]

        return self._result(
            values,
            {
                "has_opening_bar": True,
                "has_bars_after_open": True,
                "up_bias": state.bias == Bias.UP,
                "down_bias": state.bias == Bias.DOWN,
                "entry_signal": latest_signal is not None,
            },
            latest_signal,
        )

    def _base_values(self):
        return {
            "session_anchor": BREAK_1M_SESSION_ANCHOR,
            "pullback_dollars": BREAK_1M_PULLBACK_DOLLARS,
            "bounce_dollars": BREAK_1M_BOUNCE_DOLLARS,
            "breakout_buffer": BREAK_1M_BREAKOUT_BUFFER,
            "stop_buffer": BREAK_1M_STOP_BUFFER,
            "reward_risk_ratio": BREAK_1M_REWARD_RISK_RATIO,
            "use_close_confirmation": BREAK_1M_USE_CLOSE_CONFIRMATION,
        }

    def _latest_session_bars(self, bars):
        if not bars:
            return []

        parsed = [(parse_bar_datetime(bar["time"]), bar) for bar in bars]
        latest_date = parsed[-1][0].date()
        anchor = parse_anchor_time(BREAK_1M_SESSION_ANCHOR)
        return [
            bar for bar_time, bar in parsed
            if bar_time.date() == latest_date and bar_time.time() >= anchor
        ]

    def _update(self, state, bar, opening_high, opening_low):
        high = float(bar["high"])
        low = float(bar["low"])
        close = float(bar["close"])
        reference_high = close if BREAK_1M_USE_CLOSE_CONFIRMATION else high
        reference_low = close if BREAK_1M_USE_CLOSE_CONFIRMATION else low
        broke_high = reference_high >= opening_high + BREAK_1M_BREAKOUT_BUFFER
        broke_low = reference_low <= opening_low - BREAK_1M_BREAKOUT_BUFFER

        if state.bias == Bias.NEUTRAL:
            if broke_high and broke_low:
                if close >= (opening_high + opening_low) / 2:
                    self._switch_up(state, high)
                else:
                    self._switch_down(state, low)
                return None
            if broke_high:
                self._switch_up(state, high)
                return None
            if broke_low:
                self._switch_down(state, low)
                return None
        elif state.bias == Bias.UP and broke_low:
            self._switch_down(state, low)
            return None
        elif state.bias == Bias.DOWN and broke_high:
            self._switch_up(state, high)
            return None

        if state.bias == Bias.UP:
            return self._update_long(state, bar)
        if state.bias == Bias.DOWN:
            return self._update_short(state, bar)
        return None

    def _update_long(self, state, bar):
        high = float(bar["high"])
        low = float(bar["low"])
        close = float(bar["close"])

        if state.setup == SetupState.UP_WAIT_PULLBACK:
            state.up_peak = max(state.up_peak, high)
            if state.up_peak - low >= BREAK_1M_PULLBACK_DOLLARS:
                state.pullback_low = low
                state.setup = SetupState.UP_WAIT_BOUNCE
            return None

        if state.setup == SetupState.UP_WAIT_BOUNCE:
            state.pullback_low = min(state.pullback_low, low)
            if high - state.pullback_low >= BREAK_1M_BOUNCE_DOLLARS:
                stop = state.pullback_low - BREAK_1M_STOP_BUFFER
                risk = close - stop
                if risk <= 0:
                    return None
                signal = self._signal(
                    "CALL",
                    close,
                    stop,
                    close + risk * BREAK_1M_REWARD_RISK_RATIO,
                )
                self._switch_up(state, high)
                return signal
        return None

    def _update_short(self, state, bar):
        high = float(bar["high"])
        low = float(bar["low"])
        close = float(bar["close"])

        if state.setup == SetupState.DOWN_WAIT_BOUNCE:
            state.down_trough = min(state.down_trough, low)
            if high - state.down_trough >= BREAK_1M_PULLBACK_DOLLARS:
                state.bounce_high = high
                state.setup = SetupState.DOWN_WAIT_DROP
            return None

        if state.setup == SetupState.DOWN_WAIT_DROP:
            state.bounce_high = max(state.bounce_high, high)
            if state.bounce_high - low >= BREAK_1M_BOUNCE_DOLLARS:
                stop = state.bounce_high + BREAK_1M_STOP_BUFFER
                risk = stop - close
                if risk <= 0:
                    return None
                signal = self._signal(
                    "PUT",
                    close,
                    stop,
                    close - risk * BREAK_1M_REWARD_RISK_RATIO,
                )
                self._switch_down(state, low)
                return signal
        return None

    def _signal(self, direction, entry, stop, target):
        risk = abs(entry - stop)
        levels = {
            "entry_price": entry,
            "stop_price": stop,
            "target_price": target,
            "risk_per_share": risk,
        }
        return {
            "action": "BUY",
            "underlying": UNDERLYING_SYMBOL,
            "direction": direction,
            "reason": (
                f"Break1M {direction}: retracement >= "
                f"${BREAK_1M_PULLBACK_DOLLARS:.2f}, continuation >= "
                f"${BREAK_1M_BOUNCE_DOLLARS:.2f}, R:R 1:"
                f"{BREAK_1M_REWARD_RISK_RATIO:g}"
            ),
            "levels": levels,
        }

    @staticmethod
    def _switch_up(state, high):
        state.bias = Bias.UP
        state.setup = SetupState.UP_WAIT_PULLBACK
        state.up_peak = high
        state.pullback_low = None
        state.down_trough = None
        state.bounce_high = None

    @staticmethod
    def _switch_down(state, low):
        state.bias = Bias.DOWN
        state.setup = SetupState.DOWN_WAIT_BOUNCE
        state.down_trough = low
        state.bounce_high = None
        state.up_peak = None
        state.pullback_low = None

    @staticmethod
    def _result(values, conditions, signal=None):
        return {"values": values, "conditions": conditions, "signal": signal}

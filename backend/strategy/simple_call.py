from ..config import UNDERLYING_SYMBOL
from .base import BaseStrategy


class SimpleCallStrategy(BaseStrategy):
    name = "simple_call"

    def calculate(self, context):
        return {
            "values": {},
            "conditions": {
                "always_buy_call": True,
            },
            "signal": {
                "action": "BUY",
                "underlying": UNDERLYING_SYMBOL,
                "direction": "CALL",
                "reason": "entry signal",
            },
        }

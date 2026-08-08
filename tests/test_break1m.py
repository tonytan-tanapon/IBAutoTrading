import unittest

from backend.offline_strategy_runner import make_context
from backend.strategy.break1m import Break1MStrategy


def bar(minute, high, low, close):
    return {
        "time": f"2026-08-03 09:{minute:02d}:00",
        "open": close,
        "high": high,
        "low": low,
        "close": close,
        "volume": 100,
    }


class Break1MStrategyTests(unittest.TestCase):
    def setUp(self):
        self.strategy = Break1MStrategy()

    def snapshot(self, bars):
        return self.strategy.get_snapshot(make_context(bars))

    def test_long_after_break_pullback_and_bounce(self):
        bars = [
            bar(30, 101, 99, 100),
            bar(31, 102, 100.5, 101.5),
            bar(32, 103, 102, 102.5),
            bar(33, 102.5, 100.5, 101),
            bar(34, 102.6, 100.5, 102.5),
        ]

        result = self.snapshot(bars)

        self.assertEqual(result["signal"]["direction"], "CALL")
        levels = result["signal"]["levels"]
        self.assertAlmostEqual(levels["stop_price"], 100.45)
        self.assertAlmostEqual(
            levels["target_price"] - levels["entry_price"],
            levels["entry_price"] - levels["stop_price"],
        )

    def test_short_after_break_bounce_and_drop(self):
        bars = [
            bar(30, 101, 99, 100),
            bar(31, 99.5, 98, 98.5),
            bar(32, 98.5, 97, 97.5),
            bar(33, 99, 97.5, 98.5),
            bar(34, 99, 96.9, 97),
        ]

        result = self.snapshot(bars)

        self.assertEqual(result["signal"]["direction"], "PUT")
        levels = result["signal"]["levels"]
        self.assertAlmostEqual(levels["stop_price"], 99.05)
        self.assertAlmostEqual(
            levels["entry_price"] - levels["target_price"],
            levels["stop_price"] - levels["entry_price"],
        )

    def test_up_bias_reverses_when_opening_low_breaks(self):
        bars = [
            bar(30, 101, 99, 100),
            bar(31, 102, 100, 101.5),
            bar(32, 100, 98, 98.5),
        ]

        result = self.snapshot(bars)

        self.assertEqual(result["values"]["bias"], "down")
        self.assertEqual(result["values"]["state"], "down_wait_bounce")
        self.assertIsNone(result["signal"])

    def test_only_latest_bar_emits_signal(self):
        bars = [
            bar(30, 101, 99, 100),
            bar(31, 102, 100.5, 101.5),
            bar(32, 103, 102, 102.5),
            bar(33, 102.5, 100.5, 101),
            bar(34, 102.6, 100.5, 102.5),
            bar(35, 103, 102, 102.8),
        ]

        self.assertIsNone(self.snapshot(bars)["signal"])


if __name__ == "__main__":
    unittest.main()

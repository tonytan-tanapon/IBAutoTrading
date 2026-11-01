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

    def test_high_break_without_full_pullback_has_no_signal(self):
        bars = [
            bar(30, 101, 99, 100),
            bar(31, 102, 100.5, 101.5),
            bar(32, 103, 101.1, 102.5),
        ]

        result = self.snapshot(bars)

        self.assertEqual(result["values"]["bias"], "up")
        self.assertEqual(result["values"]["state"], "up_wait_pullback")
        self.assertIsNone(result["signal"])

    def test_full_pullback_without_full_bounce_has_no_signal(self):
        bars = [
            bar(30, 101, 99, 100),
            bar(31, 102, 100.5, 101.5),
            bar(32, 103, 102, 102.5),
            bar(33, 102.5, 100.5, 101),
            bar(34, 102.4, 100.5, 102),
        ]

        result = self.snapshot(bars)

        self.assertEqual(result["values"]["state"], "up_wait_bounce")
        self.assertIsNone(result["signal"])

    def test_touching_opening_high_counts_as_breakout(self):
        bars = [
            bar(30, 101, 99, 100),
            bar(31, 101, 99.5, 100.5),
        ]

        result = self.snapshot(bars)

        self.assertEqual(result["values"]["bias"], "up")
        self.assertEqual(result["values"]["state"], "up_wait_pullback")

    def test_bar_breaking_both_sides_uses_close_vs_opening_midpoint(self):
        upper_close = self.snapshot([
            bar(30, 101, 99, 100),
            bar(31, 102, 98, 100.5),
        ])
        lower_close = self.snapshot([
            bar(30, 101, 99, 100),
            bar(31, 102, 98, 99.5),
        ])

        self.assertEqual(upper_close["values"]["bias"], "up")
        self.assertEqual(lower_close["values"]["bias"], "down")

    def test_can_emit_a_second_signal_in_same_session(self):
        bars = [
            bar(30, 101, 99, 100),
            bar(31, 102, 100.5, 101.5),
            bar(32, 103, 102, 102.5),
            bar(33, 102.5, 100.5, 101),
            bar(34, 102.6, 100.5, 102.5),  # first CALL
            bar(35, 105, 102.7, 104.5),
            bar(36, 104, 102.5, 103),
            bar(37, 104.6, 102.5, 104.5),  # second CALL
        ]

        first = self.snapshot(bars[:5])
        second = self.snapshot(bars)

        self.assertEqual(first["signal"]["direction"], "CALL")
        self.assertEqual(second["signal"]["direction"], "CALL")


if __name__ == "__main__":
    unittest.main()

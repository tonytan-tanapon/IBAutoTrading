import unittest
from datetime import datetime, timedelta

from ib_auto_trading.strategies.sma import sma_crossover
from ib_auto_trading.historical_signals import (
    completed_bars,
    previous_4h_range_history,
    sma_signal_history,
)
from ib_auto_trading.strategies.previous_4h_range import (
    previous_4h_range_signal,
)
from ib_auto_trading.strategy_runner import StrategyRunner


class FakeHistoricalClient:
    def __init__(self, closes: list[float]) -> None:
        self.closes = closes

    def is_ready(self) -> bool:
        return True

    def request_historical_bars(
        self,
        symbol: str,
        duration: str,
        bar_size: str,
    ):
        return [
            {
                "close": close,
                "high": close + 1,
                "low": close - 1,
            }
            for close in self.closes
        ]

    def get_market_data(self, symbol):
        return {"last": self.closes[-1]}

    def subscribe_market_data(self, symbol):
        return self.get_market_data(symbol)


class SmaStrategyTests(unittest.TestCase):
    def test_buy_signal_on_upward_crossover(self) -> None:
        result = sma_crossover([10, 10, 10, 10, 9, 9, 12], 2, 4)
        self.assertEqual(result.signal, "BUY")

    def test_runner_updates_signal_only_state(self) -> None:
        client = FakeHistoricalClient([10, 10, 10, 10, 9, 9, 12])
        runner = StrategyRunner(client)
        runner.configure("SPY", 2, 4, 60)

        status = runner.check_now()

        self.assertEqual(status["last_signal"], "BUY")
        self.assertEqual(status["symbol"], "SPY")
        self.assertEqual(status["bar_count"], 7)
        self.assertFalse(status["enabled"])

    def test_previous_4h_range_call_levels(self) -> None:
        result = previous_4h_range_signal(
            price=116,
            previous_high=110,
            previous_low=100,
        )
        self.assertEqual(result.signal, "CALL")
        self.assertEqual(result.call_entry, 115)
        self.assertEqual(result.call_target, 120)
        self.assertEqual(result.call_stop, 110)

    def test_previous_4h_range_put_levels(self) -> None:
        result = previous_4h_range_signal(
            price=94,
            previous_high=110,
            previous_low=100,
        )
        self.assertEqual(result.signal, "PUT")
        self.assertEqual(result.put_entry, 95)
        self.assertEqual(result.put_target, 90)
        self.assertEqual(result.put_stop, 100)

    def test_runner_uses_previous_completed_4h_bar(self) -> None:
        client = FakeHistoricalClient([100, 105, 116])
        runner = StrategyRunner(client)
        runner.configure(
            "SPY",
            5,
            20,
            60,
            strategy_type="PREVIOUS_4H_RANGE",
        )

        status = runner.check_now()

        self.assertEqual(status["previous_high"], 106)
        self.assertEqual(status["previous_low"], 104)
        self.assertEqual(status["last_signal"], "CALL")

    def test_sma_history_calculates_each_bar_without_future_data(self) -> None:
        bars = [
            {
                "time": str(index),
                "open": close - 0.5,
                "high": close + 1,
                "low": close - 1,
                "close": close,
            }
            for index, close in enumerate([10, 10, 10, 10, 9, 9, 12])
        ]

        rows = sma_signal_history(bars, 2, 4)

        self.assertEqual(rows[-1]["time"], "6")
        self.assertEqual(rows[-1]["signal"], "BUY")

    def test_range_history_uses_the_previous_bar_levels(self) -> None:
        bars = [
            {
                "time": "1",
                "open": 104,
                "high": 110,
                "low": 100,
                "close": 105,
            },
            {
                "time": "2",
                "open": 105,
                "high": 118,
                "low": 104,
                "close": 116,
            },
        ]

        rows = previous_4h_range_history(bars)

        self.assertEqual(rows[0]["previous_high"], 110)
        self.assertEqual(rows[0]["previous_low"], 100)
        self.assertEqual(rows[0]["signal"], "CALL")

    def test_completed_bars_keeps_friday_bar_on_sunday(self) -> None:
        bars = [{"time": "20260612 12:00:00", "close": 100}]
        sunday = datetime(
            2026,
            6,
            14,
            12,
            0,
        )

        result = completed_bars(bars, timedelta(hours=4), now=sunday)

        self.assertEqual(result, bars)

    def test_completed_bars_removes_only_the_open_bar(self) -> None:
        bars = [
            {"time": "20260615 09:30:00", "close": 100},
            {"time": "20260615 12:00:00", "close": 101},
        ]
        during_latest_bar = datetime(
            2026,
            6,
            15,
            13,
            0,
        )

        result = completed_bars(
            bars,
            timedelta(hours=4),
            now=during_latest_bar,
        )

        self.assertEqual(result, bars[:-1])


if __name__ == "__main__":
    unittest.main()

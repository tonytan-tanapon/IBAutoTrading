import threading
import unittest
from dataclasses import dataclass

from ib_auto_trading.risk import RiskSettings
from ib_auto_trading.services.account_service import account_summary
from ib_auto_trading.services.order_service import estimated_price, validate_risk
from ib_auto_trading.services.position_service import position_snapshots


class FakeClient:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.accounts = ["DU123456"]
        self.buying_power = 50_000.0
        self.buying_power_currency = "USD"
        self.positions = {
            "SPY": {
                "account": "DU123456",
                "symbol": "SPY",
                "quantity": 2,
                "average_cost": 400.0,
                "market_price": None,
                "market_value": None,
                "unrealized_pnl": None,
            }
        }
        self.market_data = {
            "SPY": {
                "symbol": "SPY",
                "bid": 409.5,
                "ask": 410.0,
                "last": 409.75,
                "close": 408.0,
            }
        }
        self.ready = True
        self.paper = True

    def is_ready(self) -> bool:
        return self.ready

    def is_paper_account(self) -> bool:
        return self.paper

    def get_market_data(self, symbol=None):
        if symbol:
            return self.market_data.get(symbol.upper())
        return list(self.market_data.values())

    def subscribe_market_data(self, symbol):
        return self.market_data[symbol.upper()]


@dataclass
class FakeOrder:
    symbol: str = "SPY"
    action: str = "BUY"
    quantity: int = 2
    order_type: str = "MKT"
    limit_price: float | None = None


class ServiceTests(unittest.TestCase):
    def test_account_summary_uses_client_state(self) -> None:
        client = FakeClient()

        summary = account_summary(client)

        self.assertTrue(summary["connected"])
        self.assertEqual(summary["accounts"], ["DU123456"])
        self.assertTrue(summary["paper_account"])
        self.assertEqual(summary["buying_power"], 50_000.0)

    def test_position_snapshot_calculates_market_value_and_pnl(self) -> None:
        client = FakeClient()

        positions = position_snapshots(client)

        self.assertEqual(len(positions), 1)
        self.assertEqual(positions[0]["market_price"], 409.75)
        self.assertEqual(positions[0]["market_value"], 819.5)
        self.assertEqual(positions[0]["unrealized_pnl"], 19.5)

    def test_estimated_price_uses_ask_for_market_buy(self) -> None:
        client = FakeClient()

        price = estimated_price(FakeOrder(action="BUY"), client)

        self.assertEqual(price, 410.0)

    def test_risk_rejects_non_paper_account(self) -> None:
        client = FakeClient()
        client.paper = False
        settings = RiskSettings(paper_only=True)

        with self.assertRaises(PermissionError):
            validate_risk(FakeOrder(), 820.0, client, settings)

    def test_risk_rejects_order_above_value_limit(self) -> None:
        client = FakeClient()
        settings = RiskSettings(max_order_value=100.0)

        with self.assertRaises(ValueError):
            validate_risk(FakeOrder(), 820.0, client, settings)


if __name__ == "__main__":
    unittest.main()

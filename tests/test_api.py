import unittest

from fastapi.testclient import TestClient

from ib_auto_trading.api import app
from ib_auto_trading.dependencies import get_ib_client


class FakeIBClient:
    def __init__(self) -> None:
        self.accounts = ["DU123456"]
        self.buying_power = 100_000.0
        self.buying_power_currency = "USD"
        self.last_error = None
        self.orders = []

    def is_ready(self) -> bool:
        return True

    def is_paper_account(self) -> bool:
        return True

    def get_market_data(self, symbol=None):
        quote = {
            "symbol": "SPY",
            "bid": 499.0,
            "ask": 500.0,
            "last": 499.5,
            "close": 498.0,
            "updated_at": None,
        }
        return quote if symbol else [quote]

    def get_orders(self):
        return list(self.orders)

    def submit_order(
        self,
        symbol,
        action,
        quantity,
        order_type,
        limit_price=None,
    ):
        self.orders.append(
            {
                "order_id": 10,
                "symbol": symbol,
                "action": action,
                "quantity": quantity,
                "order_type": order_type,
                "limit_price": limit_price,
                "status": "PendingSubmit",
            }
        )
        return 10


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fake_client = FakeIBClient()
        app.dependency_overrides[get_ib_client] = lambda: self.fake_client
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_account_summary_marks_paper_account(self) -> None:
        response = self.client.get("/api/account/summary")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["paper_account"])

    def test_order_requires_preview_before_submit(self) -> None:
        preview_response = self.client.post(
            "/api/orders/preview",
            json={
                "symbol": "SPY",
                "action": "BUY",
                "quantity": 1,
                "order_type": "MKT",
                "limit_price": None,
            },
        )
        self.assertEqual(preview_response.status_code, 200)

        submit_response = self.client.post(
            "/api/orders/submit",
            json={"preview_id": preview_response.json()["preview_id"]},
        )
        self.assertEqual(submit_response.status_code, 200)
        self.assertEqual(submit_response.json()["order_id"], 10)

    def test_preview_rejects_order_above_quantity_limit(self) -> None:
        response = self.client.post(
            "/api/orders/preview",
            json={
                "symbol": "SPY",
                "action": "BUY",
                "quantity": 101,
                "order_type": "LMT",
                "limit_price": 1,
            },
        )
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()

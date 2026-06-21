from __future__ import annotations

import threading
import time
from decimal import Decimal
from typing import Any

from ibapi.client import EClient
from ibapi.contract import Contract
from ibapi.order import Order
from ibapi.wrapper import EWrapper


def stock_contract(symbol: str) -> Contract:
    contract = Contract()
    contract.symbol = symbol.upper()
    contract.secType = "STK"
    contract.exchange = "SMART"
    contract.currency = "USD"
    return contract


class IBClient(EWrapper, EClient):
    ACCOUNT_SUMMARY_REQUEST_ID = 1

    def __init__(self) -> None:
        EClient.__init__(self, self)
        self.ready = threading.Event()
        self.accounts_ready = threading.Event()
        self.positions_ready = threading.Event()
        self.thread: threading.Thread | None = None
        self.lock = threading.RLock()
        self.last_error: str | None = None
        self.next_order_id: int | None = None
        self.accounts: list[str] = []
        self.buying_power: float | None = None
        self.buying_power_currency: str | None = None
        self.positions: dict[str, dict[str, Any]] = {}
        self.market_data: dict[str, dict[str, Any]] = {}
        self.orders: dict[int, dict[str, Any]] = {}
        self._market_requests: dict[int, str] = {}
        self._symbol_requests: dict[str, int] = {}
        self._historical_requests: dict[int, list[dict[str, Any]]] = {}
        self._historical_events: dict[int, threading.Event] = {}
        self._next_request_id = 100
        self._update_callback: Any = None
        self._log_callback: Any = None

    def set_update_callback(self, callback: Any) -> None:
        self._update_callback = callback

    def set_log_callback(self, callback: Any) -> None:
        self._log_callback = callback

    def _notify_update(self) -> None:
        if self._update_callback:
            self._update_callback()

    def _log(self, message: str) -> None:
        if self._log_callback:
            self._log_callback(message)

    def connect_to_tws(
        self,
        host: str = "127.0.0.1",
        port: int = 7497,
        client_id: int = 10,
        timeout: float = 5,
    ) -> bool:
        if self.is_ready():
            self._log("TWS connection already active")
            return True

        self._log(f"Connecting to TWS {host}:{port} with client ID {client_id}")
        self.ready.clear()
        self.accounts_ready.clear()
        self.last_error = None

        try:
            self.connect(host, port, clientId=client_id)
        except OSError as exc:
            self.last_error = str(exc)
            self._log(f"TWS connection failed: {exc}")
            return False

        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

        if not self.ready.wait(timeout):
            self.last_error = self.last_error or "Timed out waiting for TWS"
            self._log(f"TWS connection failed: {self.last_error}")
            self.disconnect_from_tws()
            return False

        self.accounts_ready.wait(timeout=2)
        self.request_positions()
        self.reqOpenOrders()
        self._log("TWS connected; requested account, positions, and open orders")
        self._notify_update()
        return True

    def disconnect_from_tws(self) -> None:
        was_connected = self.isConnected()
        self.ready.clear()

        if was_connected:
            self._log("Disconnecting from TWS")
            self.cancelAccountSummary(self.ACCOUNT_SUMMARY_REQUEST_ID)
            for request_id in list(self._market_requests):
                self.cancelMktData(request_id)
            self.cancelPositions()
            self.disconnect()

        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1)

        with self.lock:
            self.thread = None
            self.buying_power = None
            self.buying_power_currency = None
            self.positions.clear()
            self.market_data.clear()
            self._market_requests.clear()
            self._symbol_requests.clear()
            self._historical_requests.clear()
            self._historical_events.clear()
        if was_connected:
            self._log("Disconnected from TWS and cleared live state")
        self._notify_update()

    def is_ready(self) -> bool:
        return self.isConnected() and self.ready.is_set()

    def is_paper_account(self) -> bool:
        with self.lock:
            return bool(self.accounts) and all(
                account.upper().startswith("DU") for account in self.accounts
            )

    def request_positions(self) -> None:
        if not self.is_ready():
            return
        self.positions_ready.clear()
        with self.lock:
            self.positions.clear()
        self._log("Requesting positions from TWS")
        self.reqPositions()

    def subscribe_market_data(self, symbol: str) -> dict[str, Any]:
        symbol = symbol.strip().upper()
        if not symbol:
            raise ValueError("Symbol is required")
        if not self.is_ready():
            raise RuntimeError("TWS is not connected")

        with self.lock:
            existing_id = self._symbol_requests.get(symbol)
            if existing_id is not None:
                self._log(f"Market data already subscribed for {symbol}")
                return dict(self.market_data[symbol])

            request_id = self._next_request_id
            self._next_request_id += 1
            self._market_requests[request_id] = symbol
            self._symbol_requests[symbol] = request_id
            self.market_data[symbol] = {
                "symbol": symbol,
                "bid": None,
                "ask": None,
                "last": None,
                "close": None,
                "updated_at": None,
            }

        self.reqMktData(
            request_id,
            stock_contract(symbol),
            "",
            False,
            False,
            [],
        )
        self._log(f"Subscribed to market data for {symbol}")
        self._notify_update()
        return self.get_market_data(symbol)

    def unsubscribe_market_data(self, symbol: str) -> bool:
        symbol = symbol.strip().upper()
        with self.lock:
            request_id = self._symbol_requests.pop(symbol, None)
        if request_id is None:
            self._log(f"Market data was not subscribed for {symbol}")
            return False
            self._market_requests.pop(request_id, None)
            self.market_data.pop(symbol, None)

        if self.isConnected():
            self.cancelMktData(request_id)
        self._log(f"Unsubscribed from market data for {symbol}")
        self._notify_update()
        return True

    def get_market_data(self, symbol: str | None = None) -> Any:
        with self.lock:
            if symbol:
                data = self.market_data.get(symbol.upper())
                return dict(data) if data else None
            return [dict(item) for item in self.market_data.values()]

    def request_historical_bars(
        self,
        symbol: str,
        duration: str = "2 D",
        bar_size: str = "1 min",
        timeout: float = 15,
    ) -> list[dict[str, Any]]:
        if not self.is_ready():
            raise RuntimeError("TWS is not connected")

        self._log(
            f"Loading historical bars for {symbol.strip().upper()} "
            f"({duration}, {bar_size})"
        )
        with self.lock:
            request_id = self._next_request_id
            self._next_request_id += 1
            event = threading.Event()
            self._historical_requests[request_id] = []
            self._historical_events[request_id] = event

        self.reqHistoricalData(
            request_id,
            stock_contract(symbol),
            "",
            duration,
            bar_size,
            "TRADES",
            1,
            1,
            False,
            [],
        )

        if not event.wait(timeout):
            self.cancelHistoricalData(request_id)
            with self.lock:
                self._historical_requests.pop(request_id, None)
                self._historical_events.pop(request_id, None)
            self._log(f"Historical bars timed out for {symbol.strip().upper()}")
            raise TimeoutError("Timed out waiting for historical bars")

        with self.lock:
            bars = self._historical_requests.pop(request_id, [])
            self._historical_events.pop(request_id, None)
        self._log(f"Loaded {len(bars)} historical bars for {symbol.strip().upper()}")
        return bars

    def submit_order(
        self,
        symbol: str,
        action: str,
        quantity: int,
        order_type: str,
        limit_price: float | None = None,
    ) -> int:
        if not self.is_ready():
            raise RuntimeError("TWS is not connected")
        if self.next_order_id is None:
            raise RuntimeError("No valid order ID is available")

        order = Order()
        order.action = action.upper()
        order.orderType = order_type.upper()
        order.totalQuantity = quantity
        order.transmit = True
        if order.orderType == "LMT":
            if limit_price is None:
                raise ValueError("Limit price is required")
            order.lmtPrice = limit_price

        with self.lock:
            order_id = self.next_order_id
            self.next_order_id += 1
            self.orders[order_id] = {
                "order_id": order_id,
                "symbol": symbol.upper(),
                "action": order.action,
                "quantity": quantity,
                "order_type": order.orderType,
                "limit_price": limit_price,
                "status": "PendingSubmit",
                "filled": 0.0,
                "remaining": float(quantity),
                "average_fill_price": 0.0,
            }

        self.placeOrder(order_id, stock_contract(symbol), order)
        self._log(
            f"Submitted {order.orderType} {order.action} order "
            f"{order_id} for {quantity} {symbol.upper()}"
        )
        self._notify_update()
        return order_id

    def cancel_order(self, order_id: int) -> None:
        if not self.is_ready():
            raise RuntimeError("TWS is not connected")
        self.cancelOrder(order_id)
        self._log(f"Cancel requested for order {order_id}")

    def get_orders(self) -> list[dict[str, Any]]:
        with self.lock:
            return [dict(order) for order in self.orders.values()]

    def nextValidId(self, order_id: int) -> None:
        self.next_order_id = order_id
        self.ready.set()
        self.reqAccountSummary(
            self.ACCOUNT_SUMMARY_REQUEST_ID,
            "All",
            "BuyingPower",
        )
        self._log("Received next valid order ID and requested account summary")
        self._notify_update()

    def managedAccounts(self, accounts_list: str) -> None:
        with self.lock:
            self.accounts = [
                account.strip() for account in accounts_list.split(",") if account.strip()
            ]
        self.accounts_ready.set()
        self._log(f"Managed accounts loaded: {', '.join(self.accounts) or 'none'}")
        self._notify_update()

    def connectionClosed(self) -> None:
        self.ready.clear()
        self._log("TWS connection closed")
        self._notify_update()

    def error(
        self,
        req_id: int,
        error_code: int,
        error_string: str,
        advanced_order_reject_json: str = "",
    ) -> None:
        informational_codes = {2104, 2106, 2107, 2108, 2158}
        if error_code not in informational_codes:
            self.last_error = f"{error_code}: {error_string}"
            print(f"TWS error {self.last_error}")
            self._log(f"TWS error {self.last_error}")
            self._notify_update()

    def accountSummary(
        self,
        req_id: int,
        account: str,
        tag: str,
        value: str,
        currency: str,
    ) -> None:
        if tag == "BuyingPower":
            with self.lock:
                self.buying_power = float(value)
                self.buying_power_currency = currency
            self._log(f"Account buying power updated: {value} {currency}")
            self._notify_update()

    def position(
        self,
        account: str,
        contract: Contract,
        position: Decimal,
        avg_cost: float,
    ) -> None:
        quantity = float(position)
        if quantity == 0:
            return
        with self.lock:
            self.positions[contract.symbol] = {
                "account": account,
                "symbol": contract.symbol,
                "quantity": quantity,
                "average_cost": avg_cost,
                "market_price": None,
                "market_value": None,
                "unrealized_pnl": None,
            }
        self._log(f"Position loaded: {contract.symbol} {float(position):g}")
        self._notify_update()

    def positionEnd(self) -> None:
        self.positions_ready.set()
        self.cancelPositions()
        self._log(f"Positions request complete: {len(self.positions)} open positions")
        self._notify_update()

    def tickPrice(
        self,
        req_id: int,
        tick_type: int,
        price: float,
        attrib: Any,
    ) -> None:
        field_by_tick = {1: "bid", 2: "ask", 4: "last", 9: "close"}
        field = field_by_tick.get(tick_type)
        if field is None or price < 0:
            return

        with self.lock:
            symbol = self._market_requests.get(req_id)
            if symbol is None:
                return
            self.market_data[symbol][field] = price
            self.market_data[symbol]["updated_at"] = time.time()
        self._notify_update()

    def historicalData(self, req_id: int, bar: Any) -> None:
        with self.lock:
            bars = self._historical_requests.get(req_id)
            if bars is None:
                return
            bars.append(
                {
                    "time": str(bar.date),
                    "open": float(bar.open),
                    "high": float(bar.high),
                    "low": float(bar.low),
                    "close": float(bar.close),
                    "volume": float(bar.volume),
                }
            )

    def historicalDataEnd(self, req_id: int, start: str, end: str) -> None:
        with self.lock:
            event = self._historical_events.get(req_id)
        if event:
            event.set()

    def openOrder(
        self,
        order_id: int,
        contract: Contract,
        order: Order,
        order_state: Any,
    ) -> None:
        with self.lock:
            current = self.orders.setdefault(order_id, {"order_id": order_id})
            current.update(
                {
                    "symbol": contract.symbol,
                    "action": order.action,
                    "quantity": float(order.totalQuantity),
                    "order_type": order.orderType,
                    "limit_price": getattr(order, "lmtPrice", None),
                    "status": order_state.status or current.get("status", "Unknown"),
                }
            )
        self._log(
            f"Open order loaded: {order_id} {contract.symbol} "
            f"{current.get('status', 'Unknown')}"
        )
        self._notify_update()

    def orderStatus(
        self,
        order_id: int,
        status: str,
        filled: Decimal,
        remaining: Decimal,
        avg_fill_price: float,
        perm_id: int,
        parent_id: int,
        last_fill_price: float,
        client_id: int,
        why_held: str,
        mkt_cap_price: float,
    ) -> None:
        with self.lock:
            current = self.orders.setdefault(order_id, {"order_id": order_id})
            current.update(
                {
                    "status": status,
                    "filled": float(filled),
                    "remaining": float(remaining),
                    "average_fill_price": avg_fill_price,
                }
            )
        self._log(
            f"Order {order_id} status: {status}, "
            f"filled {float(filled):g}, remaining {float(remaining):g}"
        )
        self._notify_update()

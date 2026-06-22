import threading

import time
from .ib_app import App
from .strategy.strategy import Strategy
from .option_selector import OptionSelector

from .config import (
    UNDERLYING_SYMBOL,
    UNDERLYING_ASSET_TYPE,
    HISTORICAL_SYMBOL,
    HISTORICAL_ASSET_TYPE,
    HISTORICAL_DURATION,
    HISTORICAL_BAR_SIZE,
    DRY_RUN_ORDERS,
    IGNORE_OPEN_ORDERS_FOR_TEST,
    FORCE_SEND_ONCE,
    TEST_ORDER_QUANTITY,
    TEST_ORDER_LIMIT_PRICE,
    IGNORE_POSITIONS_FOR_TEST,
)

class TradingEngine:
    def __init__(self):
        self.ib = App()
        self.thread = None
        self.running = False
        self.strategy = Strategy()
        self.historical_data = []
        self.order_in_flight = False
        self.pending_order_id = None
        self.option_chain = None
        self.option_selector = OptionSelector()

        self.force_order_sent = False

    def start(self):
        self.ib.connect("127.0.0.1", 7497, clientId=0)

        self.thread = threading.Thread(target=self.ib.run, daemon=True)
        self.thread.start()

        if not self.ib.connected_event.wait(timeout=10):
            raise RuntimeError("TWS connection timeout")

        print("connected_event set")
        print("isConnected after wait:", self.ib.isConnected())

        self.running = True

    def load_initial_state(self):
        self.load_account_once()
        self.load_positions_once()
        self.load_open_orders_once()
        self.historical_data = self.load_historical_once(
            HISTORICAL_SYMBOL,
            asset_type=HISTORICAL_ASSET_TYPE,
            duration=HISTORICAL_DURATION,
            bar_size=HISTORICAL_BAR_SIZE,
        )

        self.option_chain = self.load_option_chain_once(UNDERLYING_SYMBOL)
    
    
    def subscribe_market_data(self, symbol: str = "EUR/USD", asset_type: str = "forex"):
        if not self.is_ready():
            raise RuntimeError("Engine is not connected")

        self.ib.request_market_data(symbol, asset_type=asset_type)

    def run_forever(self):
        while self.is_ready():
            has_update = self.ib.market_data_event.wait(timeout=1)

            if not has_update:
                continue

            self.ib.market_data_event.clear()

            context = self.get_strategy_context()
            signal = self.strategy.check_signal(context)

            self.manage_orders(context, signal)

    def stop(self):
        self.running = False
        self.ib.disconnect()
        print("Disconnected")

    def is_ready(self):
        return self.running and self.ib.connected_event.is_set()

    
 

    def get_strategy_context(self):
        return {
            "market_data": self.ib.market_data,
            "account_summary": self.ib.account_summary,
            "positions": self.ib.positions,
            "orders": self.ib.orders,
            "historical_data": self.historical_data,
            "option_chain": self.option_chain,
        }

    def manage_orders(self, context, signal=None):
        DONE_STATUSES = {"Filled", "Cancelled", "Inactive", "ApiCancelled", "Rejected"}

        if self.pending_order_id is not None:
            status = self.ib.last_order_status.get(self.pending_order_id)

            if status in DONE_STATUSES:
                self.order_in_flight = False
                self.pending_order_id = None
            else:
                print(f"Order {self.pending_order_id} in flight ({status}). Skip new signal.")
                return

        if self.order_in_flight:
            print("Order in flight. Skip new signal.")
            return

        positions = context["positions"]
        orders = context["orders"]

        if orders and not IGNORE_OPEN_ORDERS_FOR_TEST:
            print("There is open order. Do not send duplicate order.")
            return

        if positions and not IGNORE_POSITIONS_FOR_TEST:
            print("There is position. Use signal as exit decision.")

            if signal and signal.get("action") == "SELL":
                print("Close position")

            return

        if signal:
            if FORCE_SEND_ONCE and self.force_order_sent:
                print("Force order already sent. Skip.")
                return

            option_contract_info = self.option_selector.select_contract(signal, context)
            quantity = TEST_ORDER_QUANTITY
            limit_price = TEST_ORDER_LIMIT_PRICE

            print("Selected option:", option_contract_info)
            print(f"Order settings: quantity={quantity} limit_price={limit_price}")

            if DRY_RUN_ORDERS:
                print("DRY RUN: would submit option order")
                print("signal:", signal)
                print("contract:", option_contract_info)
                return

            self.order_in_flight = True

            try:
                order_id = self.ib.place_limit_option_order(
                    symbol=option_contract_info["symbol"],
                    expiry=option_contract_info["expiry"],
                    strike=option_contract_info["strike"],
                    right=option_contract_info["right"],
                    action=signal["action"],
                    quantity=quantity,
                    limit_price=limit_price,
                )

                self.pending_order_id = order_id
                self.force_order_sent = True

                print("Submitted option order", order_id)

            except Exception:
                self.order_in_flight = False
                self.pending_order_id = None
                raise
            

            

    def load_account_once(self, timeout: float = 10):
        if not self.is_ready():
            raise RuntimeError("Engine is not connected")

        self.ib.request_account_summary()

        if not self.ib.account_summary_event.wait(timeout=timeout):
            raise RuntimeError("Account summary timeout")

        self.ib.cancelAccountSummary(self.ib.account_summary_req_id)

        print("Account summary loaded")
        
        return self.ib.account_summary
    
    def load_positions_once(self, timeout: float = 10):
        if not self.is_ready():
            raise RuntimeError("Engine is not connected")

        self.ib.request_positions()

        if not self.ib.positions_event.wait(timeout=timeout):
            raise RuntimeError("Positions timeout")

        self.ib.cancelPositions()

        print("Positions loaded")
        return self.ib.positions
    

    def load_open_orders_once(self, timeout: float = 10):
        if not self.is_ready():
            raise RuntimeError("Engine is not connected")

        self.ib.request_open_orders()

        if not self.ib.open_orders_event.wait(timeout=timeout):
            raise RuntimeError("Open orders timeout")

        print("Open orders loaded")
        return self.ib.orders
    

    def load_historical_once(
        self,
        symbol: str = "EUR/USD",
        asset_type: str = "forex",
        duration: str = "2 D",
        bar_size: str = "1 min",
        timeout: float = 15,
    ):
        if not self.is_ready():
            raise RuntimeError("Engine is not connected")

        req_id, event = self.ib.request_historical_data(
            symbol=symbol,
            asset_type=asset_type,
            duration=duration,
            bar_size=bar_size,
        )

        if not event.wait(timeout=timeout):
            self.ib.cancelHistoricalData(req_id)
            raise RuntimeError("Historical data timeout")

        bars = self.ib.historical_data.get(req_id, [])

        print(f"Historical loaded: {symbol} {len(bars)} bars")
        return bars
    

    def load_option_chain_once(self, symbol: str = "SPY", timeout: float = 15):
        if not self.is_ready():
            raise RuntimeError("Engine is not connected")

        details_req_id, details_event = self.ib.request_contract_details(symbol, "stock")

        if not details_event.wait(timeout=timeout):
            raise RuntimeError("Contract details timeout")

        details = self.ib.contract_details.get(details_req_id, [])

        if not details:
            raise RuntimeError(f"No contract details for {symbol}")

        underlying_con_id = details[0].contract.conId

        chain_req_id, chain_event = self.ib.request_option_chain(
            underlying_symbol=symbol,
            underlying_con_id=underlying_con_id,
        )

        if not chain_event.wait(timeout=timeout):
            raise RuntimeError("Option chain timeout")

        chains = self.ib.option_chains.get(chain_req_id, [])

        print(f"Option chain loaded: {symbol}, groups={len(chains)}")
        return {
            "symbol": symbol,
            "underlying_con_id": underlying_con_id,
            "chains": chains,
        }

    def run_once(self):
        self.subscribe_market_data(
            UNDERLYING_SYMBOL,
            asset_type=UNDERLYING_ASSET_TYPE,
        )

        if not self.ib.market_data_event.wait(timeout=10):
            raise RuntimeError("Market data timeout")

        self.ib.market_data_event.clear()

        context = self.get_strategy_context()
        signal = self.strategy.check_signal(context)

        self.manage_orders(context, signal)
        self.wait_for_order_ack(timeout=10)

    def wait_for_order_ack(self, timeout: float = 10):
        if self.pending_order_id is None:
            return

        deadline = time.time() + timeout

        while time.time() < deadline:
            status = self.ib.last_order_status.get(self.pending_order_id)
            order = self.ib.orders.get(self.pending_order_id)

            if status or order:
                print("Order acknowledged")
                print("order_id:", self.pending_order_id)
                print("status:", status)
                print("order:", order)
                return

            time.sleep(0.25)

        print("No order acknowledgement received before timeout")

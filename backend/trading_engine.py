import threading

from .ib_app import App
from .strategy.registry import create_strategy
from .option_selector import OptionSelector
from .option_pricing import OptionPricingService
from .risk_manager import RiskManager
from .order_manager import OrderManager
from concurrent.futures import ThreadPoolExecutor

from .config import (
    IB_HOST,
    IB_PORT,
    IB_CLIENT_ID,
    UNDERLYING_SYMBOL,
    UNDERLYING_ASSET_TYPE,
    HISTORICAL_SYMBOL,
    HISTORICAL_ASSET_TYPE,
    HISTORICAL_DURATION,
    HISTORICAL_BAR_SIZE,
    HISTORICAL_TIMEOUT,
    SHOW_STRATEGY_SNAPSHOT,
    STRATEGY_NAME,
)

class TradingEngine:
    def __init__(self):
        self.ib = App()
        self.thread = None
        self.running = False
        self.strategy = create_strategy(STRATEGY_NAME)
        self.historical_data = []
        self.option_chain = None
        self.option_selector = OptionSelector()
        self.option_pricing = OptionPricingService(
            self.ib,
            self.raise_request_error_if_any,
        )
        self.risk_manager = RiskManager()
        self.order_manager = OrderManager(
            ib=self.ib,
            option_selector=self.option_selector,
            option_pricing=self.option_pricing,
            risk_manager=self.risk_manager,
        )

    def start(self):
        self.ib.connect(IB_HOST, IB_PORT, clientId=IB_CLIENT_ID)
        self.thread = threading.Thread(target=self.ib.run, daemon=True)
        self.thread.start()

        if not self.ib.connected_event.wait(timeout=10):
            raise RuntimeError("TWS connection timeout")

        print("connected_event set")
        print("isConnected after wait:", self.ib.isConnected())

        self.running = True

    def load_initial_state(self):
        with ThreadPoolExecutor(max_workers=5) as executor:
            account_future = executor.submit(self.load_account_once)
            positions_future = executor.submit(self.load_positions_once)
            open_orders_future = executor.submit(self.load_open_orders_once)

            historical_future = executor.submit(
                self.load_historical_once,
                HISTORICAL_SYMBOL,
                asset_type=HISTORICAL_ASSET_TYPE,
                duration=HISTORICAL_DURATION,
                bar_size=HISTORICAL_BAR_SIZE,
                timeout=HISTORICAL_TIMEOUT,
            )

            option_chain_future = executor.submit(
                self.load_option_chain_once,
                UNDERLYING_SYMBOL,
            )

            account_future.result()
            positions_future.result()
            open_orders_future.result()
            self.historical_data = historical_future.result()
            self.option_chain = option_chain_future.result()
    
    
    def subscribe_market_data(self, symbol: str, asset_type: str ):
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
            snapshot = self.strategy.get_snapshot(context)
            self.print_strategy_snapshot(snapshot)
            signal = snapshot["signal"]

            self.order_manager.manage_orders(context, signal)

    def stop(self):
        self.running = False
        self.ib.disconnect()
        print("Disconnected")

    def is_ready(self):
        return self.running and self.ib.connected_event.is_set()

    def raise_request_error_if_any(self, req_id: int, label: str):
        error = self.ib.request_errors.get(req_id)

        if error:
            raise RuntimeError(
                f"{label} error code={error['code']} message={error['message']}"
            )
 

    def get_strategy_context(self):
        return {
            "market_data": self.ib.market_data,
            "account_summary": self.ib.account_summary,
            "positions": self.ib.positions,
            "orders": self.ib.orders,
            "historical_data": self.historical_data,
            "option_chain": self.option_chain,
        }

    def get_strategy_snapshot(self):
        context = self.get_strategy_context()
        return self.strategy.get_snapshot(context)

    def print_strategy_snapshot(self, snapshot):
        if not SHOW_STRATEGY_SNAPSHOT:
            return

        compact_snapshot = self.compact_snapshot(snapshot)

        print()
        print("=====Strategy Snapshot====")
        self.print_table(self.flatten_snapshot(compact_snapshot))

    def print_table(self, rows):
        if not rows:
            print("(empty)")
            return

        key_width = min(max(len(row[0]) for row in rows), 48)

        print(f"{'Field':<{key_width}} | Value")
        print(f"{'-' * key_width}-+-{'-' * 60}")

        for key, value in rows:
            print(f"{key:<{key_width}} | {value}")

    def flatten_snapshot(self, value, prefix=""):
        rows = []

        if isinstance(value, dict):
            for key, item in value.items():
                next_prefix = f"{prefix}.{key}" if prefix else str(key)
                rows.extend(self.flatten_snapshot(item, next_prefix))
            return rows

        rows.append((prefix, self.format_snapshot_value(value)))
        return rows

    def format_snapshot_value(self, value):
        if isinstance(value, float):
            return f"{value:.4f}"

        return str(value)

    def compact_snapshot(self, value):
        if isinstance(value, dict):
            return {
                key: self.compact_snapshot(item)
                for key, item in value.items()
            }

        if isinstance(value, list):
            if len(value) <= 5:
                return [self.compact_snapshot(item) for item in value]

            return {
                "count": len(value),
                "latest": self.compact_snapshot(value[-1]),
            }

        return value

    def load_account_once(self, timeout: float = 10):
        if not self.is_ready():
            raise RuntimeError("Engine is not connected")

        self.ib.request_account_summary()

        if not self.ib.account_summary_event.wait(timeout=timeout):
            self.raise_request_error_if_any(
                self.ib.account_summary_req_id,
                "Account summary",
            )
            raise RuntimeError("Account summary timeout")

        self.raise_request_error_if_any(
            self.ib.account_summary_req_id,
            "Account summary",
        )

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
        symbol: str ,
        asset_type: str ,
        duration: str ,
        bar_size: str ,
        timeout: float ,
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
            self.raise_request_error_if_any(req_id, "Historical data")
            self.ib.cancelHistoricalData(req_id)
            raise RuntimeError("Historical data timeout")

        self.raise_request_error_if_any(req_id, "Historical data")

        bars = self.ib.historical_data.get(req_id, [])

        print(f"Historical loaded: {symbol} {len(bars)} bars")
        return bars
    

    def load_option_chain_once(self, symbol: str = "SPY", timeout: float = 15):
        if not self.is_ready():
            raise RuntimeError("Engine is not connected")

        details_req_id, details_event = self.ib.request_contract_details(symbol, "stock")

        if not details_event.wait(timeout=timeout):
            self.raise_request_error_if_any(details_req_id, "Contract details")
            raise RuntimeError("Contract details timeout")

        self.raise_request_error_if_any(details_req_id, "Contract details")

        details = self.ib.contract_details.get(details_req_id, [])

        if not details:
            raise RuntimeError(f"No contract details for {symbol}")

        underlying_con_id = details[0].contract.conId

        chain_req_id, chain_event = self.ib.request_option_chain(
            underlying_symbol=symbol,
            underlying_con_id=underlying_con_id,
        )

        if not chain_event.wait(timeout=timeout):
            self.raise_request_error_if_any(chain_req_id, "Option chain")
            raise RuntimeError("Option chain timeout")

        self.raise_request_error_if_any(chain_req_id, "Option chain")

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
        snapshot = self.strategy.get_snapshot(context)
        self.print_strategy_snapshot(snapshot)
        signal = snapshot["signal"]

        self.order_manager.manage_orders(context, signal)
        self.order_manager.wait_for_order_ack(timeout=10)

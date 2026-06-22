import time

from .config import (
    DRY_RUN_ORDERS,
    ENABLE_EXIT_LOGIC,
    EXIT_ON_SELL_SIGNAL,
    FORCE_SEND_ONCE,
    IGNORE_OPEN_ORDERS_FOR_TEST,
    IGNORE_POSITIONS_FOR_TEST,
    OPTION_MULTIPLIER,
    OPTION_POSITION_AVG_COST_INCLUDES_MULTIPLIER,
    STOP_LOSS_PERCENT,
    TAKE_PROFIT_PERCENT,
)


class OrderManager:
    DONE_STATUSES = {"Filled", "Cancelled", "Inactive", "ApiCancelled", "Rejected"}

    def __init__(self, ib, option_selector, option_pricing, risk_manager):
        self.ib = ib
        self.option_selector = option_selector
        self.option_pricing = option_pricing
        self.risk_manager = risk_manager
        self.order_in_flight = False
        self.pending_order_id = None
        self.force_order_sent = False

    def manage_orders(self, context, signal=None):
        if self.pending_order_id is not None:
            status = self.ib.last_order_status.get(self.pending_order_id)

            if status in self.DONE_STATUSES:
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
            self.manage_existing_positions(positions, signal)
            return

        self.option_pricing.unsubscribe_missing_position_quotes([])
        self.manage_entry_signal(context, signal)

    def manage_entry_signal(self, context, signal=None):
        if not signal:
            return

        if signal.get("action") != "BUY":
            print(f"Entry skipped for non-BUY signal: {signal}")
            return

        if FORCE_SEND_ONCE and self.force_order_sent:
            print("Force order already sent. Skip.")
            return

        option_contract_info = self.option_selector.select_contract(signal, context)
        limit_price = self.option_pricing.get_limit_price(
            option_contract_info,
            signal["action"],
        )
        quantity = self.risk_manager.calculate_order_quantity(context, limit_price)

        print(f"Order settings: quantity={quantity} limit_price={limit_price}")

        if quantity <= 0:
            print("Risk check: quantity is 0. Skip order.")
            return

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

    def manage_existing_positions(self, positions, signal=None):
        print("There is position. Check exit decision.")

        managed_any = False
        active_option_contracts = []

        for position in positions.values():
            if position.get("sec_type") != "OPT":
                print("Skip non-option position:", position)
                continue

            managed_any = True
            active_option_contracts.append(
                self.position_to_option_contract_info(position)
            )
            self.manage_option_position(position, signal)

            if self.order_in_flight:
                return

        self.option_pricing.unsubscribe_missing_position_quotes(active_option_contracts)

        if not managed_any:
            print("No option position managed. Skip new entry while positions exist.")

    def manage_option_position(self, position, signal=None):
        option_contract_info = self.position_to_option_contract_info(position)
        close_action = "SELL" if position["quantity"] > 0 else "BUY"
        close_quantity = int(abs(position["quantity"]))

        if close_quantity <= 0:
            return

        current_price = self.option_pricing.get_persistent_limit_price(
            option_contract_info,
            close_action,
        )
        entry_price = self.get_position_entry_price(position)
        pnl_percent = ((current_price - entry_price) / entry_price) * 100

        if position["quantity"] < 0:
            pnl_percent *= -1

        exit_reason = self.get_exit_reason(pnl_percent, signal)

        print(
            "Position check: "
            f"contract={option_contract_info} entry={entry_price} "
            f"current={current_price} pnl={pnl_percent:.2f}%"
        )

        if not exit_reason:
            print("No exit condition met.")
            return

        print(f"Exit condition met: {exit_reason}")

        if DRY_RUN_ORDERS:
            print("DRY RUN: would submit exit option order")
            print("action:", close_action)
            print("quantity:", close_quantity)
            print("limit_price:", current_price)
            print("contract:", option_contract_info)
            return

        self.order_in_flight = True

        try:
            order_id = self.ib.place_limit_option_order(
                symbol=option_contract_info["symbol"],
                expiry=option_contract_info["expiry"],
                strike=option_contract_info["strike"],
                right=option_contract_info["right"],
                action=close_action,
                quantity=close_quantity,
                limit_price=current_price,
            )

            self.pending_order_id = order_id
            print("Submitted exit option order", order_id)

        except Exception:
            self.order_in_flight = False
            self.pending_order_id = None
            raise

    def position_to_option_contract_info(self, position):
        required_fields = ["symbol", "expiry", "strike", "right"]
        missing_fields = [field for field in required_fields if not position.get(field)]

        if missing_fields:
            raise RuntimeError(
                f"Option position missing contract fields: {missing_fields}"
            )

        return {
            "symbol": position.get("underlying_symbol") or position["symbol"].split()[0],
            "sec_type": "OPT",
            "expiry": position["expiry"],
            "strike": float(position["strike"]),
            "right": position["right"],
            "exchange": "SMART",
            "currency": position.get("currency", "USD"),
        }

    def get_position_entry_price(self, position) -> float:
        avg_cost = float(position["avg_cost"])

        if OPTION_POSITION_AVG_COST_INCLUDES_MULTIPLIER:
            avg_cost = avg_cost / OPTION_MULTIPLIER

        if avg_cost <= 0:
            raise RuntimeError(f"Invalid position avg_cost: {position['avg_cost']}")

        return round(avg_cost, 2)

    def get_exit_reason(self, pnl_percent: float, signal=None):
        if ENABLE_EXIT_LOGIC:
            if STOP_LOSS_PERCENT > 0 and pnl_percent <= -STOP_LOSS_PERCENT:
                return f"stop_loss {pnl_percent:.2f}% <= -{STOP_LOSS_PERCENT}%"

            if TAKE_PROFIT_PERCENT > 0 and pnl_percent >= TAKE_PROFIT_PERCENT:
                return f"take_profit {pnl_percent:.2f}% >= {TAKE_PROFIT_PERCENT}%"

        if (
            EXIT_ON_SELL_SIGNAL
            and signal
            and signal.get("action") == "SELL"
        ):
            return "strategy_sell_signal"

        return None

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

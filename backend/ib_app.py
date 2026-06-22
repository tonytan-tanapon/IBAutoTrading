from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.order import Order

from datetime import datetime
from .contracts import stock_contract, forex_contract, option_contract
from .constants import TICK_PRICE_TYPES
import threading


class App(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)

        self.next_order_id = None
        self.req_id_to_symbol = {}
        self.next_request_id = 1
        self.market_data = {}
        self.positions = {}
        self.account_summary = {}
        self.orders = {}
        self.errors = []
        self.connected_event = threading.Event()
        self.market_data_event = threading.Event()

        self.account_summary_event = threading.Event()
        self.account_summary_req_id = 9001
        self.positions_event = threading.Event()        
        self.open_orders_event = threading.Event()

        self.historical_data = {}
        self.historical_events = {}
        self.historical_req_id_to_symbol = {}

        self.last_order_status = {}

        self.contract_details = {}
        self.contract_details_events = {}

        self.option_chains = {}
        self.option_chain_events = {}
    
    def nextValidId(self, order_id: int):
        print(f"Connected. Next order id: {order_id}")
        self.next_order_id = order_id
        self.connected_event.set()

    def request_market_data(self, symbol: str = "EUR/USD", asset_type: str = "forex"):
        if asset_type == "stock":
            contract, symbol_key = stock_contract(symbol)
        elif asset_type == "forex":
            contract, symbol_key = forex_contract(symbol)
        else:
            raise ValueError("asset_type must be stock or forex")

        req_id = self.next_request_id
        self.next_request_id += 1
        self.req_id_to_symbol[req_id] = symbol_key

        self.reqMarketDataType(1)
        self.reqMktData(req_id, contract, "", False, False, [])

    
    def tickPrice(self, req_id, tick_type, price, attrib):
        tick_name = TICK_PRICE_TYPES.get(tick_type)

        if tick_name is None:
            return

        symbol = self.req_id_to_symbol.get(req_id, "UNKNOWN")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

        self.market_data.setdefault(symbol, {})
        self.market_data[symbol][tick_name] = price
        self.market_data[symbol]["updated_at"] = now

        self.market_data_event.set()

        #print(f"{now} {symbol} {tick_name} price={price}")

    ####################
    ## accountSummary ##
    ####################
    def request_account_summary(self):
        self.account_summary_event.clear()
        self.account_summary.clear()

        self.reqAccountSummary(
            self.account_summary_req_id,
            "All",
            "BuyingPower,NetLiquidation,AvailableFunds",

        )

    def accountSummary(self, req_id, account, tag, value, currency):
        self.account_summary.setdefault(account, {})
        self.account_summary[account][tag] = {
            "value": value,
            "currency": currency,
        }

        print(f"accountSummary account={account} {tag}={value} {currency}")

    def accountSummaryEnd(self, req_id):
        self.account_summary_event.set()

    #################
    ## POSITION
    ################
    def request_positions(self):
        self.positions_event.clear()
        self.positions.clear()

        self.reqPositions()

    def position(self, account, contract, position, avgCost):
        quantity = float(position)

        if quantity == 0:
            return

        if contract.secType == "CASH":
            symbol = f"{contract.symbol}/{contract.currency}"
        else:
            symbol = contract.symbol

        self.positions[symbol] = {
            "account": account,
            "symbol": symbol,
            "sec_type": contract.secType,
            "currency": contract.currency,
            "quantity": quantity,
            "avg_cost": avgCost,
        }

        print(f"position {symbol} qty={quantity} avg_cost={avgCost}")

    def positionEnd(self):
        self.positions_event.set()
        
    ##############
    ### request_open_orders
    #########################
    def request_open_orders(self):
        self.open_orders_event.clear()
        self.orders.clear()

        self.reqOpenOrders()

    def openOrder(self, order_id, contract, order, order_state):
        self.orders[order_id] = {
            "order_id": order_id,
            "symbol": contract.symbol,
            "sec_type": contract.secType,
            "currency": contract.currency,
            "action": order.action,
            "order_type": order.orderType,
            "total_quantity": float(order.totalQuantity),
            "limit_price": getattr(order, "lmtPrice", None),
            "status": order_state.status,
        }

        print(
            f"openOrder id={order_id} "
            f"{order.action} {order.totalQuantity} {contract.symbol} "
            f"{order.orderType} status={order_state.status}"
        )

    def bind_manual_orders(self):
        self.reqAutoOpenOrders(True)

    def openOrderEnd(self):
        self.open_orders_event.set()


    ######################
    ### Historical 
    #####################
    def request_historical_data(
        self,
        symbol: str = "EUR/USD",
        asset_type: str = "forex",
        duration: str = "2 D",
        bar_size: str = "1 min",
    ):
        if asset_type == "stock":
            contract, symbol_key = stock_contract(symbol)
        elif asset_type == "forex":
            contract, symbol_key = forex_contract(symbol)
        else:
            raise ValueError("asset_type must be stock or forex")

        req_id = self.next_request_id
        self.next_request_id += 1

        event = threading.Event()

        self.historical_data[req_id] = []
        self.historical_events[req_id] = event
        self.historical_req_id_to_symbol[req_id] = symbol_key

        self.reqHistoricalData(
            req_id,
            contract,
            "",          # endDateTime: empty = now
            duration,
            bar_size,
            "MIDPOINT",  # forex นิยมใช้ MIDPOINT
            1,           # useRTH
            1,           # formatDate
            False,       # keepUpToDate
            [],
        )

        return req_id, event
    

    def historicalData(self, req_id, bar):
        self.historical_data.setdefault(req_id, [])
        self.historical_data[req_id].append(
            {
                "time": str(bar.date),
                "open": float(bar.open),
                "high": float(bar.high),
                "low": float(bar.low),
                "close": float(bar.close),
                "volume": float(bar.volume),
            }
        )

    def historicalDataEnd(self, req_id, start, end):
        event = self.historical_events.get(req_id)
        if event:
            event.set()

    #####################
    #### place Order 
    #####################
    def place_market_order(self, symbol: str, asset_type: str, action: str, quantity: int):
        if self.next_order_id is None:
            raise RuntimeError("No next order id available")

        if asset_type == "stock":
            contract, symbol_key = stock_contract(symbol)
        elif asset_type == "forex":
            contract, symbol_key = forex_contract(symbol)
        else:
            raise ValueError("asset_type must be stock or forex")

        order = Order()
        order.action = action
        order.orderType = "MKT"
        order.totalQuantity = quantity
        order.tif = "DAY"
        order.transmit = True

        order_id = self.next_order_id
        self.next_order_id += 1

        self.placeOrder(order_id, contract, order)

        return order_id
    
    def place_limit_option_order(
        self,
        symbol: str,
        expiry: str,
        strike: float,
        right: str,
        action: str,
        quantity: int,
        limit_price: float,
    ):
        if self.next_order_id is None:
            raise RuntimeError("No next order id available")

        contract, symbol_key = option_contract(
            symbol=symbol,
            expiry=expiry,
            strike=strike,
            right=right,
        )

        order = Order()
        order.action = action.upper()
        order.orderType = "LMT"
        order.totalQuantity = quantity
        order.lmtPrice = limit_price
        order.tif = "DAY"
        order.transmit = True

        order_id = self.next_order_id
        self.next_order_id += 1

        self.placeOrder(order_id, contract, order)

        return order_id
    
    def orderStatus(
        self,
        order_id,
        status,
        filled,
        remaining,
        avgFillPrice,
        permId,
        parentId,
        lastFillPrice,
        clientId,
        whyHeld,
        mktCapPrice,
    ):
        order = self.orders.setdefault(order_id, {"order_id": order_id})

        order.update(
            {
                "status": status,
                "filled": float(filled),
                "remaining": float(remaining),
                "avg_fill_price": avgFillPrice,
                "perm_id": permId,
                "client_id": clientId,
                "last_fill_price": lastFillPrice,
                "why_held": whyHeld,
            }
        )
        self.last_order_status[order_id] = status

        print(
            f"orderStatus id={order_id} status={status} "
            f"filled={float(filled)} remaining={float(remaining)} "
            f"avg={avgFillPrice}"
        )
    

    ##################
    #### Option chain 
    ####################
    def request_contract_details(self, symbol: str, asset_type: str = "stock"):
        if asset_type == "stock":
            contract, symbol_key = stock_contract(symbol)
        else:
            raise ValueError("Only stock contract details supported for now")

        req_id = self.next_request_id
        self.next_request_id += 1

        event = threading.Event()

        self.contract_details[req_id] = []
        self.contract_details_events[req_id] = event

        self.reqContractDetails(req_id, contract)

        return req_id, event
    
    def contractDetails(self, req_id, contract_details):
        self.contract_details.setdefault(req_id, [])
        self.contract_details[req_id].append(contract_details)

    def contractDetailsEnd(self, req_id):
        event = self.contract_details_events.get(req_id)
        if event:
            event.set()

    def request_option_chain(self, underlying_symbol: str, underlying_con_id: int):
        req_id = self.next_request_id
        self.next_request_id += 1

        event = threading.Event()

        self.option_chains[req_id] = []
        self.option_chain_events[req_id] = event

        self.reqSecDefOptParams(
            req_id,
            underlying_symbol,
            "",
            "STK",
            underlying_con_id,
        )

        return req_id, event
    

    def securityDefinitionOptionParameter(
        self,
        req_id,
        exchange,
        underlying_con_id,
        trading_class,
        multiplier,
        expirations,
        strikes,
    ):
        self.option_chains.setdefault(req_id, [])
        self.option_chains[req_id].append(
            {
                "exchange": exchange,
                "underlying_con_id": underlying_con_id,
                "trading_class": trading_class,
                "multiplier": multiplier,
                "expirations": sorted(expirations),
                "strikes": sorted(strikes),
            }
        )

    def securityDefinitionOptionParameterEnd(self, req_id):
        event = self.option_chain_events.get(req_id)
        if event:
            event.set()

    def error(self, req_id, *args):
        if len(args) == 2:
            error_time = None
            error_code, error_string = args
            advanced_order_reject_json = ""
        elif len(args) == 3:
            error_time = None
            error_code, error_string, advanced_order_reject_json = args
        elif len(args) == 4:
            error_time, error_code, error_string, advanced_order_reject_json = args
        else:
            print(f"ERROR req_id={req_id} args={args}")
            return

        message = f"ERROR req_id={req_id} code={error_code} message={error_string}"

        if error_time is not None:
            message = f"ERROR req_id={req_id} time={error_time} code={error_code} message={error_string}"

        if advanced_order_reject_json:
            message += f" advanced={advanced_order_reject_json}"

        self.errors.append(
            {
                "req_id": req_id,
                "code": error_code,
                "message": error_string,
                "advanced": advanced_order_reject_json,
            }
        )

        if isinstance(req_id, int) and req_id >= 0:
            order = self.orders.setdefault(req_id, {"order_id": req_id})
            order["status"] = "Rejected"
            order["error_code"] = error_code
            order["error_message"] = error_string
            self.last_order_status[req_id] = "Rejected"

        print(message)

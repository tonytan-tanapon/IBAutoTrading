from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
from ibapi.order import Order

import threading
import time


class IBApp(EWrapper, EClient):

    def __init__(self):
        EClient.__init__(self, self)
        self.next_order_id = None

    def nextValidId(self, orderId):
        self.next_order_id = orderId
        print("Next Order ID:", orderId)

    def orderStatus(
        self,
        orderId,
        status,
        filled,
        remaining,
        avgFillPrice,
        permId,
        parentId,
        lastFillPrice,
        clientId,
        whyHeld,
        mktCapPrice
    ):
        print(
            f"ORDER {orderId} | "
            f"{status} | "
            f"Filled={filled} | "
            f"Remaining={remaining} | "
            f"Avg={avgFillPrice}"
        )

    def error(
        self,
        reqId,
        errorTime,
        errorCode,
        errorString,
        advancedOrderReject=""
    ):
        print(
            f"ERROR | "
            f"reqId={reqId} "
            f"time={errorTime} "
            f"code={errorCode} "
            f"msg={errorString}"
        )

        if advancedOrderReject:
            print("Advanced Reject:", advancedOrderReject)


# =========================================================
# TSLA OPTION CONTRACT
# =========================================================

def tsla_option(expiry, strike, right):

    contract = Contract()

    contract.symbol = "TSLA"
    contract.secType = "OPT"
    contract.exchange = "SMART"
    contract.currency = "USD"

    # YYYYMMDD
    contract.lastTradeDateOrContractMonth = expiry

    contract.strike = strike

    # "C" = CALL
    # "P" = PUT
    contract.right = right

    contract.multiplier = "100"

    return contract


# =========================================================
# ORDER
# =========================================================

def limit_order(action, qty, price):

    order = Order()

    order.action = action
    order.orderType = "LMT"

    order.totalQuantity = qty
    order.lmtPrice = price

    order.tif = "DAY"

    return order


# =========================================================
# RUN IB
# =========================================================

app = IBApp()

# TWS Paper Trading
app.connect(
    "127.0.0.1",
    7497,
    clientId=10
)


thread = threading.Thread(
    target=app.run,
    daemon=True
)

thread.start()


# wait for nextValidId
while app.next_order_id is None:
    time.sleep(0.1)


# =========================================================
# TEST ORDER
# =========================================================

contract = tsla_option(
    expiry="20260814",   # CHANGE THIS
    strike=350,          # CHANGE THIS
    right="C"            # C = CALL / P = PUT
)


order = limit_order(
    action="BUY",
    qty=1,
    price=1.00           # $1.00 option premium
)


order_id = app.next_order_id


print("\nSending Order")
print("-----------------------")
print("TSLA")
print("Expiry :", contract.lastTradeDateOrContractMonth)
print("Strike :", contract.strike)
print("Right  :", contract.right)
print("Qty    :", order.totalQuantity)
print("Limit  :", order.lmtPrice)
print("-----------------------")


app.placeOrder(
    order_id,
    contract,
    order
)


# keep alive to receive status
time.sleep(15)

app.disconnect()
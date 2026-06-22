# strategy.py
from ..config import UNDERLYING_SYMBOL
class Strategy:
    def check_signal(self, context):
        market_data = context["market_data"]
        account_summary = context["account_summary"]
        positions = context["positions"]
        orders = context["orders"]
        historical_data = context["historical_data"]

        # calculate something
        
        print()
        print("=====CALL Strategy====")
        # print("market_data", market_data)
        # print("account_summary", account_summary)
        # print("positions", positions)
        # print("orders", orders)

        print("historical bars", len(historical_data))

        if historical_data:
            latest_bar = historical_data[-1]
            print("latest historical bar", latest_bar)

        return {
            "action": "BUY",
            "underlying": UNDERLYING_SYMBOL,
            "direction": "CALL",
            "reason": "entry signal",
           
        }
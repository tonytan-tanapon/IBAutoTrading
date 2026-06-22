from .config import (
    MAX_CONTRACTS_PER_TRADE,
    MIN_ORDER_QUANTITY,
    OPTION_MULTIPLIER,
    RISK_PER_TRADE_PERCENT,
)


class RiskManager:
    def calculate_order_quantity(self, context, limit_price: float) -> int:
        account_value = self.get_account_value(context)

        risk_amount = account_value * (RISK_PER_TRADE_PERCENT / 100)
        contract_cost = limit_price * OPTION_MULTIPLIER

        if contract_cost <= 0:
            return 0

        quantity = int(risk_amount / contract_cost)
        quantity = min(quantity, MAX_CONTRACTS_PER_TRADE)

        if quantity < MIN_ORDER_QUANTITY:
            return 0

        return quantity

    def get_account_value(self, context) -> float:
        account_summary = context["account_summary"]

        for account_data in account_summary.values():
            net_liq = account_data.get("NetLiquidation")
            if net_liq:
                return float(net_liq["value"])

        raise RuntimeError("NetLiquidation not available")

from ibapi.contract import Contract

def option_contract(symbol: str, expiry: str, strike: float, right: str) -> tuple[Contract, str]:
    symbol = symbol.upper().strip()
    right = right.upper().strip()

    contract = Contract()
    contract.symbol = symbol
    contract.secType = "OPT"
    contract.exchange = "SMART"
    contract.currency = "USD"
    contract.lastTradeDateOrContractMonth = expiry
    contract.strike = float(strike)
    contract.right = right
    contract.multiplier = "100"

    symbol_key = f"{symbol} {expiry} {strike} {right}"

    return contract, symbol_key

def stock_contract(symbol: str = "AAPL") -> tuple[Contract, str]:
    symbol = symbol.upper().strip()

    contract = Contract()
    contract.symbol = symbol
    contract.secType = "STK"
    contract.exchange = "SMART"
    contract.currency = "USD"

    return contract, symbol


def forex_contract(symbol: str = "EUR/USD") -> tuple[Contract, str]:
    symbol = symbol.upper().strip()

    if "/" in symbol:
        cash1, cash2 = symbol.split("/")
    elif "." in symbol:
        cash1, cash2 = symbol.split(".")
    else:
        if len(symbol) != 6:
            raise ValueError("Forex symbol must be like EUR/USD, EUR.USD, or EURUSD")
        cash1 = symbol[:3]
        cash2 = symbol[3:]

    symbol_key = f"{cash1}/{cash2}"

    contract = Contract()
    contract.symbol = cash1
    contract.secType = "CASH"
    contract.exchange = "IDEALPRO"
    contract.currency = cash2

    return contract, symbol_key
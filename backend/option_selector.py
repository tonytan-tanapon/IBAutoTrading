# option_selector.py
class OptionSelector:
    def select_contract(self, signal, context):
        underlying_price = self.get_underlying_price(signal, context)

        option_chain = context["option_chain"]
        chain = self.choose_chain(option_chain)

        strike = self.choose_strike(
            underlying_price=underlying_price,
            strikes=chain["strikes"],
        )

        expiry = self.choose_expiry(chain)

        return {
            "symbol": signal["underlying"],
            "sec_type": "OPT",
            "expiry": expiry,
            "strike": strike,
            "right": "C" if signal["direction"] == "CALL" else "P",
            "exchange": "SMART",
            "currency": "USD",
        }

    def choose_chain(self, option_chain):
        chains = option_chain["chains"]

        if not chains:
            raise RuntimeError("No option chain available")

        return next((c for c in chains if c["exchange"] == "SMART"), chains[0])

    def choose_strike(self, underlying_price, strikes):
        if not strikes:
            raise RuntimeError("No option strikes available")

        return min(strikes, key=lambda strike: abs(strike - underlying_price))

    def choose_expiry(self, chain):
        expirations = chain["expirations"]

        if not expirations:
            raise RuntimeError("No option expirations available")

        return expirations[0]

    def get_underlying_price(self, signal, context):
        underlying = signal["underlying"]
        market_data = context["market_data"]

        data = market_data.get(underlying)

        if not data:
            raise RuntimeError(f"No market data for underlying {underlying}")

        bid = data.get("bid")
        ask = data.get("ask")
        last = data.get("last")
        close = data.get("close")

        if bid is not None and ask is not None:
            return (bid + ask) / 2

        if last is not None:
            return last

        if close is not None:
            return close

        raise RuntimeError(f"No usable price for underlying {underlying}")
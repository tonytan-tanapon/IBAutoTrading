from .config import (
    DRY_RUN_ORDERS,
    FALLBACK_OPTION_LIMIT_PRICE,
    OPTION_HISTORICAL_BAR_SIZE,
    OPTION_HISTORICAL_DURATION,
    OPTION_HISTORICAL_TIMEOUT,
    OPTION_PRICE_TIMEOUT,
    USE_OPTION_HISTORICAL_FALLBACK,
    USE_OPTION_MARKET_PRICE,
)


class OptionPricingService:
    def __init__(self, ib, raise_request_error_if_any):
        self.ib = ib
        self.raise_request_error_if_any = raise_request_error_if_any
        self.persistent_option_quotes = {}

    def get_contract_key(self, option_contract_info):
        return (
            option_contract_info["symbol"],
            option_contract_info["expiry"],
            float(option_contract_info["strike"]),
            option_contract_info["right"],
        )

    def get_limit_price(self, option_contract_info, action: str) -> float:
        if not USE_OPTION_MARKET_PRICE:
            return FALLBACK_OPTION_LIMIT_PRICE

        try:
            return self.load_market_limit_price_once(
                option_contract_info,
                action,
                timeout=OPTION_PRICE_TIMEOUT,
            )
        except Exception as exc:
            if USE_OPTION_HISTORICAL_FALLBACK:
                try:
                    return self.load_historical_limit_price_once(
                        option_contract_info,
                        timeout=OPTION_HISTORICAL_TIMEOUT,
                    )
                except Exception as historical_exc:
                    print(
                        "Option historical price unavailable. "
                        f"reason={historical_exc}"
                    )

            if DRY_RUN_ORDERS:
                print(
                    "Option price unavailable in dry run. "
                    f"Use fallback limit price {FALLBACK_OPTION_LIMIT_PRICE}. "
                    f"reason={exc}"
                )
                return FALLBACK_OPTION_LIMIT_PRICE

            raise

    def load_market_limit_price_once(
        self,
        option_contract_info,
        action: str,
        timeout: float,
    ) -> float:
        req_id, event = self.ib.request_option_market_data(
            symbol=option_contract_info["symbol"],
            expiry=option_contract_info["expiry"],
            strike=option_contract_info["strike"],
            right=option_contract_info["right"],
        )

        try:
            if not event.wait(timeout=timeout):
                self.raise_request_error_if_any(req_id, "Option market data")
                raise RuntimeError("Option market data timeout")

            self.raise_request_error_if_any(req_id, "Option market data")

            data = self.ib.option_market_data.get(req_id, {})
            bid = data.get("bid")
            ask = data.get("ask")

            if not bid or not ask or bid <= 0 or ask <= 0:
                raise RuntimeError(f"Invalid option bid/ask: bid={bid} ask={ask}")

            limit_price = round((bid + ask) / 2, 2)

            print(
                "Option market price: "
                f"action={action} bid={bid} ask={ask} limit={limit_price}"
            )

            return limit_price
        finally:
            self.ib.cancelMktData(req_id)

    def get_persistent_limit_price(self, option_contract_info, action: str) -> float:
        if not USE_OPTION_MARKET_PRICE:
            return FALLBACK_OPTION_LIMIT_PRICE

        try:
            return self.load_persistent_market_limit_price(
                option_contract_info,
                action,
                timeout=OPTION_PRICE_TIMEOUT,
            )
        except Exception as exc:
            if USE_OPTION_HISTORICAL_FALLBACK:
                try:
                    return self.load_historical_limit_price_once(
                        option_contract_info,
                        timeout=OPTION_HISTORICAL_TIMEOUT,
                    )
                except Exception as historical_exc:
                    print(
                        "Option historical price unavailable. "
                        f"reason={historical_exc}"
                    )

            if DRY_RUN_ORDERS:
                print(
                    "Persistent option price unavailable in dry run. "
                    f"Use fallback limit price {FALLBACK_OPTION_LIMIT_PRICE}. "
                    f"reason={exc}"
                )
                return FALLBACK_OPTION_LIMIT_PRICE

            raise

    def load_persistent_market_limit_price(
        self,
        option_contract_info,
        action: str,
        timeout: float,
    ) -> float:
        key = self.get_contract_key(option_contract_info)
        req_id = self.persistent_option_quotes.get(key)

        if req_id is None:
            req_id, _ = self.ib.request_option_market_data(
                symbol=option_contract_info["symbol"],
                expiry=option_contract_info["expiry"],
                strike=option_contract_info["strike"],
                right=option_contract_info["right"],
            )
            self.persistent_option_quotes[key] = req_id
            print(f"Subscribed option quote: key={key} req_id={req_id}")

        data = self.wait_for_valid_option_quote(req_id, timeout)
        bid = data["bid"]
        ask = data["ask"]
        limit_price = round((bid + ask) / 2, 2)

        print(
            "Persistent option market price: "
            f"action={action} bid={bid} ask={ask} limit={limit_price}"
        )

        return limit_price

    def wait_for_valid_option_quote(self, req_id: int, timeout: float):
        data = self.ib.option_market_data.get(req_id, {})

        if self.has_valid_bid_ask(data):
            return data

        event = self.ib.option_market_data_events.get(req_id)

        if event is None:
            raise RuntimeError(f"No option market data event for req_id={req_id}")

        if not event.wait(timeout=timeout):
            self.raise_request_error_if_any(req_id, "Option market data")
            raise RuntimeError("Option market data timeout")

        self.raise_request_error_if_any(req_id, "Option market data")

        data = self.ib.option_market_data.get(req_id, {})

        if not self.has_valid_bid_ask(data):
            bid = data.get("bid")
            ask = data.get("ask")
            raise RuntimeError(f"Invalid option bid/ask: bid={bid} ask={ask}")

        return data

    def has_valid_bid_ask(self, data):
        bid = data.get("bid")
        ask = data.get("ask")
        return bid is not None and ask is not None and bid > 0 and ask > 0

    def unsubscribe_missing_position_quotes(self, active_option_contracts):
        active_keys = {
            self.get_contract_key(option_contract_info)
            for option_contract_info in active_option_contracts
        }

        for key, req_id in list(self.persistent_option_quotes.items()):
            if key in active_keys:
                continue

            self.ib.cancelMktData(req_id)
            self.persistent_option_quotes.pop(key, None)
            self.ib.option_market_data.pop(req_id, None)
            self.ib.option_market_data_events.pop(req_id, None)
            print(f"Unsubscribed option quote: key={key} req_id={req_id}")

    def load_historical_limit_price_once(
        self,
        option_contract_info,
        timeout: float,
    ) -> float:
        req_id, event = self.ib.request_option_historical_data(
            symbol=option_contract_info["symbol"],
            expiry=option_contract_info["expiry"],
            strike=option_contract_info["strike"],
            right=option_contract_info["right"],
            duration=OPTION_HISTORICAL_DURATION,
            bar_size=OPTION_HISTORICAL_BAR_SIZE,
        )

        if not event.wait(timeout=timeout):
            self.raise_request_error_if_any(req_id, "Option historical data")
            self.ib.cancelHistoricalData(req_id)
            raise RuntimeError("Option historical data timeout")

        self.raise_request_error_if_any(req_id, "Option historical data")

        bars = self.ib.historical_data.get(req_id, [])

        if not bars:
            raise RuntimeError("No option historical bars")

        latest_bar = bars[-1]
        close_price = latest_bar.get("close")

        if not close_price or close_price <= 0:
            raise RuntimeError(f"Invalid option historical close: {close_price}")

        limit_price = round(close_price, 2)

        print(
            "Option historical price: "
            f"bars={len(bars)} latest={latest_bar} limit={limit_price}"
        )

        return limit_price

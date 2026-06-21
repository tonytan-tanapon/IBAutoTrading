from __future__ import annotations

from typing import Any

from ..ib_client import IBClient


def account_summary(client: IBClient) -> dict[str, Any]:
    with client.lock:
        accounts = list(client.accounts)
        buying_power = client.buying_power
        currency = client.buying_power_currency

    return {
        "connected": client.is_ready(),
        "accounts": accounts,
        "paper_account": client.is_paper_account(),
        "buying_power": buying_power,
        "currency": currency,
    }

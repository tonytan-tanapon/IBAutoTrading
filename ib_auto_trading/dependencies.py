from .ib_client import IBClient
from .strategy_runner import StrategyRunner


ib_client = IBClient()
strategy_runner = StrategyRunner(ib_client)


def get_ib_client() -> IBClient:
    return ib_client


def get_strategy_runner() -> StrategyRunner:
    return strategy_runner

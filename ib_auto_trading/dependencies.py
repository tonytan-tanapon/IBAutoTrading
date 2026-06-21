from .ib_client import IBClient
from .realtime import realtime_broadcaster
from .strategy_runner import StrategyRunner


ib_client = IBClient()
strategy_runner = StrategyRunner(ib_client)
ib_client.set_update_callback(realtime_broadcaster.notify)
ib_client.set_log_callback(realtime_broadcaster.log)
strategy_runner.set_update_callback(realtime_broadcaster.notify)
strategy_runner.set_log_callback(realtime_broadcaster.log)


def get_ib_client() -> IBClient:
    return ib_client


def get_strategy_runner() -> StrategyRunner:
    return strategy_runner

from .ema_cross import EmaCrossStrategy
from .sig_hl import SigHLStrategy
from .sig_hl_1m import SigHL1mStrategy
from .simple_call import SimpleCallStrategy


STRATEGIES = {
    EmaCrossStrategy.name: EmaCrossStrategy,
    SigHLStrategy.name: SigHLStrategy,
    SigHL1mStrategy.name: SigHL1mStrategy,
    SimpleCallStrategy.name: SimpleCallStrategy,
}


def create_strategy(name: str):
    try:
        strategy_class = STRATEGIES[name]
    except KeyError:
        available = ", ".join(sorted(STRATEGIES))
        raise ValueError(f"Unknown strategy: {name}. Available: {available}")

    return strategy_class()

from .trading_engine import TradingEngine
from .config import RUN_MODE, UNDERLYING_SYMBOL, UNDERLYING_ASSET_TYPE


def main():
    engine = TradingEngine()

    try:
        engine.start()
        engine.load_initial_state()

        if RUN_MODE == "once":
            engine.run_once()

        elif RUN_MODE == "forever":
            engine.subscribe_market_data(
                UNDERLYING_SYMBOL,
                asset_type=UNDERLYING_ASSET_TYPE,
            )
            engine.run_forever()

    except KeyboardInterrupt:
        print("Stopping...")
    finally:
        engine.stop()


if __name__ == "__main__":
    main()

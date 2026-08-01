import argparse
import csv
from pathlib import Path

from .config import STRATEGY_NAME
from .strategy.registry import create_strategy


REQUIRED_COLUMNS = ("open", "high", "low", "close")


def load_csv_bars(path):
    bars = []

    with Path(path).open(newline="") as csv_file:
        reader = csv.DictReader(csv_file)

        if reader.fieldnames is None:
            raise ValueError("CSV file is empty or missing a header row")

        missing_columns = [
            column for column in REQUIRED_COLUMNS
            if column not in reader.fieldnames
        ]

        if missing_columns:
            missing = ", ".join(missing_columns)
            raise ValueError(f"CSV missing required columns: {missing}")

        for index, row in enumerate(reader, start=1):
            time_value = row.get("time") or row.get("date") or str(index)

            bars.append(
                {
                    "time": time_value,
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": float(row.get("volume") or 0),
                }
            )

    return bars


def make_context(bars):
    return {
        "market_data": {},
        "account_summary": {},
        "positions": {},
        "orders": {},
        "historical_data": bars,
        "option_chain": None,
    }


def format_price(value):
    if value is None:
        return "-"

    return f"{float(value):.2f}"


def print_signal(index, snapshot):
    latest_bar = snapshot["latest_bar"]
    signal = snapshot["signal"]
    levels = snapshot["values"].get("levels", {})

    print(
        ",".join(
            [
                str(index),
                str(latest_bar.get("time", "")),
                format_price(latest_bar.get("close")),
                signal["direction"] if signal else "",
                signal["reason"] if signal else "",
                format_price(levels.get("long_level")),
                format_price(levels.get("short_level")),
                format_price(levels.get("atr_up")),
                format_price(levels.get("atr_dn")),
            ]
        )
    )


def run_final_snapshot(strategy, bars):
    snapshot = strategy.get_snapshot(make_context(bars))
    signal = snapshot["signal"]

    print(f"strategy: {snapshot['strategy']}")
    print(f"bars: {len(bars)}")
    print(f"latest_time: {snapshot['latest_bar'].get('time')}")
    print(f"latest_close: {format_price(snapshot['latest_bar'].get('close'))}")
    print(f"signal: {signal['direction'] if signal else 'None'}")

    levels = snapshot["values"].get("levels", {})

    if signal:
        print(f"reason: {signal['reason']}")

    if levels:
        print("levels:")

        for key, value in levels.items():
            print(f"  {key}: {format_price(value)}")

    print("conditions:")

    for key, value in snapshot["conditions"].items():
        print(f"  {key}: {value}")


def run_replay(strategy, bars, show_all):
    print(
        ",".join(
            [
                "bar",
                "time",
                "close",
                "direction",
                "reason",
                "long_level",
                "short_level",
                "atr_up",
                "atr_dn",
            ]
        )
    )

    for index in range(1, len(bars) + 1):
        snapshot = strategy.get_snapshot(make_context(bars[:index]))

        if show_all or snapshot["signal"]:
            print_signal(index, snapshot)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run a strategy offline from a CSV file without TWS."
    )
    parser.add_argument("csv_path", help="Path to CSV with OHLC bars")
    parser.add_argument(
        "--strategy",
        default=STRATEGY_NAME,
        help=f"Strategy name. Defaults to config STRATEGY_NAME ({STRATEGY_NAME}).",
    )
    parser.add_argument(
        "--mode",
        choices=("final", "replay"),
        default="replay",
        help="final prints only the last snapshot; replay evaluates each bar.",
    )
    parser.add_argument(
        "--show-all",
        action="store_true",
        help="In replay mode, print rows even when there is no signal.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    bars = load_csv_bars(args.csv_path)

    if not bars:
        raise ValueError("CSV does not contain any bars")

    strategy = create_strategy(args.strategy)

    if args.mode == "final":
        run_final_snapshot(strategy, bars)
        return

    run_replay(strategy, bars, args.show_all)


if __name__ == "__main__":
    main()

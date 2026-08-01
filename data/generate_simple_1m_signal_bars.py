import csv
from datetime import datetime, timedelta
from pathlib import Path


OUTPUT_PATH = Path(__file__).with_name("simple_1m_signal_bars.csv")


def add_bar(rows, timestamp, open_price, high, low, close):
    rows.append(
        {
            "time": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "open": round(open_price, 2),
            "high": round(high, 2),
            "low": round(low, 2),
            "close": round(close, 2),
            "volume": 1000,
        }
    )


def add_session(rows, start, start_close, end_close, high_cap, low_cap):
    steps = 240

    for index in range(steps):
        timestamp = start + timedelta(minutes=index)
        fraction = index / (steps - 1)
        close = start_close + (end_close - start_close) * fraction
        open_price = close + 0.05
        high = min(close + 1, high_cap)
        low = max(close - 1, low_cap)
        add_bar(rows, timestamp, open_price, high, low, close)


def main():
    rows = []

    add_session(
        rows,
        start=datetime(2026, 6, 22, 9, 30),
        start_close=110,
        end_close=103,
        high_cap=111,
        low_cap=102,
    )
    add_session(
        rows,
        start=datetime(2026, 6, 22, 13, 30),
        start_close=102,
        end_close=94.5,
        high_cap=103,
        low_cap=94,
    )

    add_bar(
        rows,
        datetime(2026, 6, 23, 9, 30),
        open_price=92,
        high=92,
        low=90,
        close=92,
    )
    add_bar(
        rows,
        datetime(2026, 6, 23, 9, 31),
        open_price=94.5,
        high=109,
        low=106,
        close=108.5,
    )

    with OUTPUT_PATH.open("w", newline="") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=("time", "open", "high", "low", "close", "volume"),
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {OUTPUT_PATH} ({len(rows)} bars)")


if __name__ == "__main__":
    main()

r"""Manual smoke test for downloading historical bars from TWS.

Run from the project root:
    .\.venv\Scripts\python.exe tests\manual_historical_data.py
"""

import argparse
import csv
import sys
import threading
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.ib_app import App


def parse_args():
    parser = argparse.ArgumentParser(description="Download IB historical data")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7497)
    parser.add_argument("--client-id", type=int, default=91)
    parser.add_argument("--symbol", default="TSLA")
    parser.add_argument("--duration", default="2 D")
    parser.add_argument("--bar-size", default="30 mins")
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("tests/output/spy_historical.csv"),
    )
    return parser.parse_args()


def main():
    args = parse_args()
    app = App()

    print(
        f"Connecting to TWS {args.host}:{args.port} "
        f"with clientId={args.client_id}"
    )
    app.connect(args.host, args.port, clientId=args.client_id)
    api_thread = threading.Thread(target=app.run, daemon=True)
    api_thread.start()

    try:
        if not app.connected_event.wait(timeout=10):
            raise RuntimeError("TWS connection timeout")

        print(f"Connected to TWS server_version={app.serverVersion()}")

        farm_deadline = time.monotonic() + 15
        while time.monotonic() < farm_deadline:
            if any(error["code"] == 2106 for error in app.errors):
                break
            time.sleep(0.1)
        else:
            raise RuntimeError(
                "HMDS farm was not ready within 15s; "
                f"recent_errors={app.errors[-10:]}"
            )

        print("HMDS farm is ready")

        details_req_id, details_completed = app.request_contract_details(
            args.symbol,
            "stock",
        )
        if not details_completed.wait(timeout=15):
            raise RuntimeError(
                "Contract details timeout; "
                f"request_error={app.request_errors.get(details_req_id)}"
            )

        details_error = app.request_errors.get(details_req_id)
        if details_error:
            raise RuntimeError(f"Contract details failed: {details_error}")

        contract_details = app.contract_details.get(details_req_id, [])
        if not contract_details:
            raise RuntimeError(f"No contract details found for {args.symbol}")

        contract = contract_details[0].contract
        print(
            "Resolved contract: "
            f"conId={contract.conId} symbol={contract.symbol} "
            f"exchange={contract.exchange} primaryExchange={contract.primaryExchange} "
            f"currency={contract.currency}"
        )

        req_id = app.get_next_request_id()
        completed = threading.Event()
        app.historical_data[req_id] = []
        app.historical_events[req_id] = completed
        app.historical_req_id_to_symbol[req_id] = args.symbol
        app.request_errors.pop(req_id, None)

        app.reqHistoricalData(
            req_id,
            contract,
            "",
            args.duration,
            args.bar_size,
            "TRADES",
            1,
            1,
            False,
            [],
        )

        print(
            f"Waiting for historical data req_id={req_id} "
            f"what_to_show=TRADES timeout={args.timeout}s"
        )
        if not completed.wait(timeout=args.timeout):
            error = app.request_errors.get(req_id)
            bars_received = len(app.historical_data.get(req_id, []))
            raise RuntimeError(
                f"Historical data timeout after {args.timeout}s; "
                f"bars_received={bars_received}; request_error={error}; "
                f"recent_errors={app.errors[-10:]}"
            )

        error = app.request_errors.get(req_id)
        if error:
            raise RuntimeError(f"Historical request failed: {error}")

        bars = app.historical_data.get(req_id, [])
        if not bars:
            raise RuntimeError("Historical request completed but returned no bars")

        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(
                csv_file,
                fieldnames=["time", "open", "high", "low", "close", "volume"],
            )
            writer.writeheader()
            writer.writerows(bars)

        print(f"Downloaded {len(bars)} bars")
        print(f"First bar: {bars[0]}")
        print(f"Last bar:  {bars[-1]}")
        print(f"Saved CSV: {args.output.resolve()}")
    finally:
        if app.isConnected():
            app.disconnect_requested = True
            app.disconnect()


if __name__ == "__main__":
    main()

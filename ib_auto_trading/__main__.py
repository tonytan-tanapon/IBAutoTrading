from .ib_client import IBClient


def main():
    app = IBClient()

    print("Connecting to TWS...")
    app.connect("127.0.0.1", 7497, clientId=1)
    app.run()

    print("Disconnected")


if __name__ == "__main__":
    main()

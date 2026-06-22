class BaseStrategy:
    name = "base"

    def calculate(self, context):
        raise NotImplementedError("Strategy must implement calculate(context)")

    def get_snapshot(self, context):
        historical_data = context.get("historical_data", [])
        result = self.calculate(context) or {}

        return {
            "strategy": self.name,
            "historical_data": historical_data,
            "latest_bar": historical_data[-1] if historical_data else None,
            "values": result.get("values", {}),
            "conditions": result.get("conditions", {}),
            "signal": result.get("signal"),
        }

    def check_signal(self, context):
        return self.get_snapshot(context)["signal"]

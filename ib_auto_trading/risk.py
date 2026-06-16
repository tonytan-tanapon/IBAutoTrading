from dataclasses import asdict, dataclass


@dataclass
class RiskSettings:
    paper_only: bool = True
    max_quantity: int = 100
    max_order_value: float = 10_000
    kill_switch: bool = False

    def to_dict(self) -> dict[str, bool | int | float]:
        return asdict(self)


risk_settings = RiskSettings()

from dataclasses import dataclass


@dataclass(frozen=True)
class Previous4HRangeResult:
    signal: str
    price: float
    high: float
    low: float
    range_size: float
    call_entry: float
    call_target: float
    call_stop: float
    put_entry: float
    put_target: float
    put_stop: float


def previous_4h_range_signal(
    price: float,
    previous_high: float,
    previous_low: float,
) -> Previous4HRangeResult:
    if previous_high <= previous_low:
        raise ValueError("Previous 4H high must be greater than low")

    range_size = previous_high - previous_low
    call_entry = previous_high + (range_size / 2)
    put_entry = previous_low - (range_size / 2)

    signal = "WAIT"
    if price > call_entry:
        signal = "CALL"
    elif price < put_entry:
        signal = "PUT"

    return Previous4HRangeResult(
        signal=signal,
        price=price,
        high=previous_high,
        low=previous_low,
        range_size=range_size,
        call_entry=call_entry,
        call_target=previous_high + range_size,
        call_stop=previous_high,
        put_entry=put_entry,
        put_target=previous_low - range_size,
        put_stop=previous_low,
    )

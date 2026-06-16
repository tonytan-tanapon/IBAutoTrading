import time
from dataclasses import asdict, dataclass
from uuid import uuid4


@dataclass(frozen=True)
class OrderPreview:
    symbol: str
    action: str
    quantity: int
    order_type: str
    limit_price: float | None
    estimated_price: float
    estimated_value: float
    expires_at: float

    def to_dict(self) -> dict[str, str | int | float | None]:
        return asdict(self)


class PreviewStore:
    def __init__(self) -> None:
        self._items: dict[str, OrderPreview] = {}

    def create(self, preview: OrderPreview) -> str:
        preview_id = uuid4().hex
        self._items[preview_id] = preview
        return preview_id

    def pop_valid(self, preview_id: str) -> OrderPreview:
        preview = self._items.pop(preview_id, None)
        if preview is None:
            raise ValueError("Preview was not found or was already used")
        if preview.expires_at < time.time():
            raise ValueError("Preview has expired")
        return preview


preview_store = PreviewStore()

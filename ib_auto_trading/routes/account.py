from fastapi import APIRouter, Depends

from ..dependencies import get_ib_client
from ..ib_client import IBClient


router = APIRouter(prefix="/api/account", tags=["account"])


@router.get("/summary")
def get_account_summary(
    client: IBClient = Depends(get_ib_client),
) -> dict[str, object]:
    return {
        "connected": client.is_ready(),
        "accounts": list(client.accounts),
        "paper_account": client.is_paper_account(),
        "buying_power": client.buying_power,
        "currency": client.buying_power_currency,
    }

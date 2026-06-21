from fastapi import APIRouter, Depends

from ..dependencies import get_ib_client
from ..ib_client import IBClient
from ..realtime import realtime_broadcaster
from ..services.account_service import account_summary


router = APIRouter(prefix="/api/account", tags=["account"])


@router.get("/summary")
def get_account_summary(
    client: IBClient = Depends(get_ib_client),
) -> dict[str, object]:
    realtime_broadcaster.log("Loading account summary")
    return account_summary(client)

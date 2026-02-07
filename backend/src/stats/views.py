from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from fastapi import status as http_status

from backend.src.auth.dependencies import RequireAdminOrShop
from backend.src.common.dependencies import PaginationParams
from backend.src.core.database import DbSession
from backend.src.core.logging import get_logger
from datetime import UTC, datetime, timedelta

from . import service

logger = get_logger(__name__)

router = APIRouter()


@router.get(
    "/export",
    summary="Выгрузка статистики в Excel",
    tags=["Statistics"],
)
async def export_statistics(
    current_user: RequireAdminOrShop,
    db: DbSession,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    shop_id: int | None = None,  # только админ может выбирать
    extended: bool = False,  # только админ
):
    pass

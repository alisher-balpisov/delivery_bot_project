import logging

import redis.asyncio as aioredis
from backend.src.auth.service import auth_by_code
from backend.src.core.database import get_db
from backend.src.core.redis import get_redis
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()

logger = logging.getLogger(__name__)


class AuthByCodeRequest(BaseModel):
    telegram_id: int
    code: str


@router.post("/by-code")
async def auth_by_code_view(
    form_data: AuthByCodeRequest,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),  # Inject Redis
):
    try:
        # Pass redis client to the service function
        result = await auth_by_code(db, redis, form_data.telegram_id, form_data.code)

        # Если результат содержит блокировку, возвращаем статус 423 Locked
        if result.get("blocked"):
            raise HTTPException(status_code=423, detail=result)

        # Если результат неуспешен (например, неверный код), возвращаем 400
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result)

        return result

    except HTTPException as e:
        # Re-raise HTTP exceptions to let FastAPI handle them
        raise e
    except Exception as e:
        logger.error(f"Error in auth_by_code_view: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

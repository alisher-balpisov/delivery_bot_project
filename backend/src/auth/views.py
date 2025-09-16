import logging

from backend.src.auth.service import auth_by_code
from backend.src.core.database import get_db
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()

logger = logging.getLogger(__name__)


class AuthByCodeRequest(BaseModel):
    telegram_id: int
    code: str


@router.post("/by-code")
async def auth_by_code_view(form_data: AuthByCodeRequest, db: AsyncSession = Depends(get_db)):
    try:
        result = await auth_by_code(db, form_data.telegram_id, form_data.code)
        return result
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error in auth_by_code_view: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

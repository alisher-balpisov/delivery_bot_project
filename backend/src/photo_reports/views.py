from backend.src.core.database import DbSession
from backend.src.photo_reports import service
from backend.src.schemas.photo_report import (
    PhotoReportCreate,
    PhotoReportListResponse,
    PhotoReportResponse,
    PhotoReportUpdate,
)
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/photo-reports", tags=["photo-reports"])


@router.post("/", response_model=PhotoReportResponse)
async def create_photo_report_endpoint(
    photo_data: PhotoReportCreate, db: DbSession
) -> PhotoReportResponse:
    """Создание нового фотоотчета для заказа."""
    try:
        return await service.create_photo_report(db, photo_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{photo_id}", response_model=PhotoReportResponse)
async def get_photo_report(photo_id: int, db: DbSession) -> PhotoReportResponse:
    """Получение фотоотчета по ID."""
    photo = await service.get_photo_report_by_id(db, photo_id)
    if not photo:
        raise HTTPException(status_code=404, detail="Фотоотчет не найден")
    return photo


@router.get("/order/{order_id}/photos", response_model=PhotoReportListResponse)
async def get_photos_by_order(
    db: DbSession,
    order_id: int,
    skip: int = 0,
    limit: int = 10,
) -> PhotoReportListResponse:
    """Получение всех фотоотчетов для конкретного заказа с пагинацией."""
    try:
        return await service.get_photo_reports_by_order_id(db, order_id, skip, limit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{photo_id}", response_model=PhotoReportResponse)
async def update_photo_report_endpoint(
    photo_id: int,
    update_data: PhotoReportUpdate,
    db: DbSession,
) -> PhotoReportResponse:
    """Обновление фотоотчета по ID."""
    try:
        photo = await service.update_photo_report(db, photo_id, update_data)
        if not photo:
            raise HTTPException(status_code=404, detail="Фотоотчет не найден")
        return photo
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{photo_id}", response_model=dict)
async def delete_photo_report_endpoint(photo_id: int, db: DbSession) -> dict:
    """Удаление фотоотчета по ID."""
    deleted = await service.delete_photo_report(db, photo_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Фотоотчет не найден")
    return {"message": "Фотоотчет успешно удален"}


@router.get("/", response_model=PhotoReportListResponse)
async def get_all_photos(
    db: DbSession,
    skip: int = 0,
    limit: int = 50,
) -> PhotoReportListResponse:
    """Получение всех фотоотчетов с пагинацией (endpoint для администраторов)."""
    return await service.get_all_photo_reports(db, skip, limit)

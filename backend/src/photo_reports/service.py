from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from src.models.order import Order
from src.models.photo_report import PhotoReport
from src.schemas.photo_report import (
    PhotoReportCreate,
    PhotoReportListResponse,
    PhotoReportResponse,
    PhotoReportUpdate,
)


async def create_photo_report(
    db: AsyncSession, photo_data: PhotoReportCreate
) -> PhotoReportResponse:
    """
    Создание нового фотоотчета, связанного с заказом.
    """
    # Проверить существование заказа
    order = await db.get(Order, photo_data.order_id)
    if not order:
        raise ValueError(f"Заказ с ID {photo_data.order_id} не найден")

    # Создать фотоотчет
    photo_report = PhotoReport(
        order_id=photo_data.order_id,
        file_id=photo_data.file_id,
        description=photo_data.description,
    )

    db.add(photo_report)
    await db.commit()
    await db.refresh(photo_report)

    return PhotoReportResponse.model_validate(photo_report)


async def get_photo_report_by_id(db: AsyncSession, photo_id: int) -> PhotoReportResponse | None:
    """
    Получение фотоотчета по его идентификатору.
    """
    photo_report = await db.get(PhotoReport, photo_id)
    if photo_report:
        return PhotoReportResponse.model_validate(photo_report)
    return None


async def get_photo_reports_by_order_id(
    db: AsyncSession, order_id: int, skip: int = 0, limit: int = 10
) -> PhotoReportListResponse:
    """
    Получение всех фотоотчетов для конкретного заказа с пагинацией.
    """
    # Подсчитать общее количество
    count_query = (
        select(func.count()).select_from(PhotoReport).where(PhotoReport.order_id == order_id)
    )
    total = await db.scalar(count_query)

    # Получить фотоотчеты
    result = await db.execute(
        select(PhotoReport)
        .where(PhotoReport.order_id == order_id)
        .order_by(PhotoReport.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    photos = result.scalars().all()

    photo_responses = [PhotoReportResponse.model_validate(photo) for photo in photos]

    return PhotoReportListResponse(photo_reports=photo_responses, total=total)


async def update_photo_report(
    db: AsyncSession, photo_id: int, update_data: PhotoReportUpdate
) -> PhotoReportResponse | None:
    """
    Обновление фотоотчета по его идентификатору.
    """
    photo_report = await db.get(PhotoReport, photo_id)
    if not photo_report:
        raise ValueError(f"Фотоотчет с ID {photo_id} не найден")

    # Обновить поля
    update_dict = update_data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(photo_report, key, value)

    await db.commit()
    await db.refresh(photo_report)

    return PhotoReportResponse.model_validate(photo_report)


async def delete_photo_report(db: AsyncSession, photo_id: int) -> bool:
    """
    Удаление фотоотчета по его идентификатору.
    Возвращает True при успешном удалении, False если не найден.
    """
    photo_report = await db.get(PhotoReport, photo_id)
    if not photo_report:
        return False

    await db.delete(photo_report)
    await db.commit()
    return True


async def get_all_photo_reports(
    db: AsyncSession, skip: int = 0, limit: int = 50
) -> PhotoReportListResponse:
    """
    Получение всех фотоотчетов с пагинацией (для администраторов).
    """
    # Подсчитать общее количество
    count_query = select(func.count()).select_from(PhotoReport)
    total = await db.scalar(count_query)

    # Получить фотоотчеты
    result = await db.execute(
        select(PhotoReport).order_by(PhotoReport.created_at.desc()).offset(skip).limit(limit)
    )
    photos = result.scalars().all()

    photo_responses = [PhotoReportResponse.model_validate(photo) for photo in photos]

    return PhotoReportListResponse(photo_reports=photo_responses, total=total)

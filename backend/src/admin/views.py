from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from backend.src.auth.dependencies import RequireAdmin
from backend.src.auth.service import mask_sensitive_data
from backend.src.common.constants import PaginatedResponse
from backend.src.common.dependencies import PaginationParams
from backend.src.common.enums import DisputeStatus, OrderStatus, UserRole
from backend.src.core.database import DbSession
from backend.src.core.logging import get_logger
from backend.src.disputes.schemas import DisputeCardResponse

from . import service
from .schemas import CreateRegistrationCodeRequest, RegistrationCodeResponse, SystemStatsResponse

logger = get_logger(__name__)


router = APIRouter()


@router.post(
    "/registration-codes",
    response_model=RegistrationCodeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_registration_code(
    request: CreateRegistrationCodeRequest,
    current_user: RequireAdmin,
    db: DbSession,
):
    """
    Генерирует одноразовый код для регистрации пользователя определенной роли.
    Доступно только администраторам.
    """
    logger.info(
        f"Администратор {current_user} инициировал генерацию кода для роли {request.role.value}"
    )
    try:
        new_code = await service.create_registration_code(
            db=db, role=request.role, created_by_admin_id=current_user.id
        )

        code = mask_sensitive_data(new_code.code)
        logger.info(
            f"Код регистрации {code} для роли {request.role.value} успешно сгенерирован "
            f"администратором {current_user}"
        )
        return new_code
    except RuntimeError as e:
        logger.error(
            f"Критическая ошибка при генерации кода для роли {request.role.value} "
            f"администратором {current_user}: {e}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера при генерации кода.")


@router.get(
    "/registration-codes",
    response_model=PaginatedResponse[RegistrationCodeResponse],
    status_code=status.HTTP_200_OK,
)
async def get_registration_codes(
    current_user: RequireAdmin,
    db: DbSession,
    pagination: PaginationParams,
    role: UserRole | None = None,
    is_used: bool | None = None,
):
    """
    Получить список кодов регистрации с пагинацией и фильтрацией.
    """
    page, limit = pagination
    return await service.get_registration_codes(
        db=db, page=page, limit=limit, role=role, is_used=is_used
    )


@router.get("/registration-codes/stats", response_model=dict, status_code=status.HTTP_200_OK)
async def get_registration_codes_stats(current_user: RequireAdmin, db: DbSession) -> dict[Any, int]:
    """
    Получить статистику кодов регистрации.
    Доступно только администраторам.
    """
    logger.info(f"Администратор ID {current_user.id} запрашивает статистику по кодам регистрации")
    try:
        stats: dict[Any, int] = await service.get_unused_registration_codes_count(db=db)
        return stats
    except Exception as e:
        logger.error(f"Ошибка при получении статистики кодов регистрации: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Не удалось получить статистику: {e!s}")


@router.get(
    "/registration-codes/{code_id}",
    response_model=RegistrationCodeResponse,
    status_code=status.HTTP_200_OK,
)
async def get_registration_code_details(
    code_id: int,
    current_user: RequireAdmin,
    db: DbSession,
):
    """
    Получить детали кода регистрации по ID.
    """
    code = await service.get_registration_code_by_id(db, code_id)
    if not code:
        raise HTTPException(status_code=404, detail="Код не найден")
    return code


@router.post(
    "/registration-codes/{code_id}/deactivate",
    response_model=RegistrationCodeResponse,
    status_code=status.HTTP_200_OK,
)
async def deactivate_registration_code(
    code_id: int,
    current_user: RequireAdmin,
    db: DbSession,
):
    """
    Деактивировать код регистрации.
    """
    try:
        return await service.deactivate_registration_code(db, code_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/system-stats", response_model=SystemStatsResponse, status_code=status.HTTP_200_OK)
async def get_system_stats(current_user: RequireAdmin, db: DbSession):
    """
    Получить системную статистику (общие метрики пользователей, заказов, споров).
    Доступно только администраторам.
    """
    logger.info(f"Администратор ID {current_user.id} запрашивает системную статистику")
    try:
        stats = await service.get_system_stats(db=db)
        return stats
    except Exception as e:
        logger.error(f"Ошибка при получении системной статистики: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Не удалось получить статистику: {e!s}")


@router.get(
    "/orders",
    response_model=PaginatedResponse[service.OrderCardResponse],
    status_code=status.HTTP_200_OK,
)
async def get_all_orders(
    db: DbSession,
    current_user: RequireAdmin,
    pagination: PaginationParams,
    status: OrderStatus | None = Query(
        None, description="Фильтр по статусу: active, inactive или blocked"
    ),
    search: str | None = Query(None, description="Поиск по имени магазина или имени пользователя"),
    current: bool | None = Query(None, description="true=активные, false=завершённые"),
):
    """
    Просмотреть все заказы системы (админ-панель).

    Примечание:
    - Этот эндпоинт предназначен для административного управления с текстовым поиском
    - Для получения истории заказов пользователя используйте GET /orders/history
    - Поддерживает поиск по названию магазина, имени курьера и описанию заказа
    """
    page, limit = pagination
    logger.info(
        f"Администратор {current_user} запрашивает список заказов: "
        f"{page=}, {limit=}, {status=}, {search=}, {current=}"
    )

    try:
        result = await service.get_all_orders(
            db=db,
            page=page,
            limit=limit,
            status=status,
            search=search,
            current=current,
        )

        logger.info(
            f"Успешно получен список заказов: {len(result.items)} элементов на странице {page}"
        )
        return result

    except Exception as e:
        logger.error(
            f"Ошибка при получении списка заказов для администратора {current_user}: {e}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Не удалось получить список заказов")


@router.get(
    "/disputes",
    response_model=PaginatedResponse[DisputeCardResponse],
    status_code=status.HTTP_200_OK,
)
async def get_all_disputes(
    db: DbSession,
    current_user: RequireAdmin,
    pagination: PaginationParams,
    status: DisputeStatus | None = Query(
        None, description="Фильтр по статусу: active, inactive или blocked"
    ),
    search: str | None = Query(None, description="Поиск по имени магазина или имени пользователя"),
):
    """
    Просмотреть все споры системы (админ-панель).

    Примечание:
    - Этот эндпоинт предназначен для административного управления с текстовым поиском
    - Позволяет искать споры по описанию, названию магазина, имени курьера и имени инициатора
    - Для получения конкретного спора используйте GET /disputes/{dispute_id}
    """
    page, limit = pagination
    logger.info(
        f"Администратор {current_user} запрашивает список споров: "
        f"{page=}, {limit=}, {status=}, {search=}"
    )

    try:
        result = await service.get_all_disputes(
            db=db,
            page=page,
            limit=limit,
            status=status,
            search=search,
        )

        logger.info(
            f"Успешно получен список споров: {len(result.items)} элементов на странице {page}"
        )
        return result

    except Exception as e:
        logger.error(
            f"Ошибка при получении списка споров для администратора {current_user}: {e}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Не удалось получить список споров")


@router.get("/shops/{shop_id}/stats/export")
async def export_shop_statistics(
    shop_id: int,
    db: DbSession,
    current_user: RequireAdmin,
    date_from: datetime = Query(..., description="Начальная дата периода"),
    date_to: datetime = Query(..., description="Конечная дата периода"),
    type: Literal["common", "advanced"] = Query(
        "common", description="Тип статистики: common - базовая, advanced - расширенная"
    ),
    from_last_payment: bool = Query(
        False,
        description="Начать с даты последней инкассации (CASH_COLLECTION) или первого заказа",
    ),
) -> StreamingResponse:
    """
    Экспорт статистики по конкретному магазину в Excel.

    Доступно только для админов.

    Common: базовая статистика по заказам
    Advanced: расширенная статистика с финансовыми деталями

    Параметр from_last_payment:
    - True: date_from игнорируется, период начинается с последней инкассации (CASH_COLLECTION)
      или с первого заказа если инкассаций не было
    - False: используется указанный date_from

    Возвращает файл: shop_{shop_name}_{type}_{date_from}_{date_to}.xlsx
    """
    logger.info(
        f"Администратор {current_user} запрашивает экспорт статистики магазина ID {shop_id}: "
        f"{date_from=}, {date_to=}, {type=}, {from_last_payment=}"
    )

    try:
        excel_file = await service.export_shop_statistics(
            db=db,
            shop_id=shop_id,
            date_from=date_from,
            date_to=date_to,
            stats_type=type,
            from_last_payment=from_last_payment,
        )

        logger.info(
            f"Успешно сгенерирован Excel-файл статистики ({type}) для магазина ID {shop_id}"
        )
        return excel_file

    except ValueError as e:
        logger.warning(f"Магазин ID {shop_id} не найден: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(
            f"Ошибка при экспорте статистики магазина ID {shop_id} "
            f"для администратора {current_user}: {e}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Не удалось сгенерировать файл статистики")


@router.get("/couriers/{courier_id}/stats/export")
async def export_courier_statistics(
    courier_id: int,
    db: DbSession,
    current_user: RequireAdmin,
    date_from: datetime = Query(..., description="Начальная дата периода"),
    date_to: datetime = Query(..., description="Конечная дата периода"),
    type: Literal["common", "advanced"] = Query(
        "common", description="Тип статистики: common - базовая, advanced - расширенная"
    ),
    from_last_payout: bool = Query(
        False, description="Начать с даты последней выплаты (PAYOUT) или первого ORDER_CREDIT"
    ),
) -> StreamingResponse:
    """
    Экспорт статистики по конкретному курьеру в Excel.

    Доступно только для админов.

    Common: базовая статистика по заказам и заработку
    Advanced: расширенная статистика с полной финансовой информацией

    Параметр from_last_payout:
    - True: date_from игнорируется, период начинается с последней выплаты (PAYOUT)
      или с первой транзакции ORDER_CREDIT если выплат не было
    - False: используется указанный date_from

    Возвращает файл: courier_{courier_name}_{type}_{date_from}_{date_to}.xlsx
    """
    logger.info(
        f"Администратор {current_user} запрашивает экспорт статистики курьера ID {courier_id}: "
        f"{date_from=}, {date_to=}, {type=}, {from_last_payout=}"
    )

    try:
        excel_file = await service.export_courier_statistics(
            db=db,
            courier_id=courier_id,
            date_from=date_from,
            date_to=date_to,
            stats_type=type,
            from_last_payout=from_last_payout,
        )

        logger.info(
            f"Успешно сгенерирован Excel-файл статистики ({type}) для курьера ID {courier_id}"
        )
        return excel_file

    except ValueError as e:
        logger.warning(f"Курьер ID {courier_id} не найден: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(
            f"Ошибка при экспорте статистики курьера ID {courier_id} "
            f"для администратора {current_user}: {e}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Не удалось сгенерировать файл статистики")


@router.get("/shops/stats/export")
async def export_all_shops_statistics(
    db: DbSession,
    current_user: RequireAdmin,
    date_from: datetime = Query(..., description="Начальная дата периода"),
    date_to: datetime = Query(..., description="Конечная дата периода"),
) -> StreamingResponse:
    """
    Экспорт статистики по всем заказам всех магазинов в Excel.

    Доступно только для админов.

    Возвращает объединённую таблицу всех заказов всех магазинов с детальной информацией.

    Возвращает файл: shops_{date_from}_{date_to}.xlsx
    """
    logger.info(
        f"Администратор {current_user} запрашивает экспорт общей статистики магазинов: "
        f"{date_from=}, {date_to=}"
    )

    try:
        excel_file = await service.export_all_shops_statistics(
            db=db,
            date_from=date_from,
            date_to=date_to,
        )

        logger.info("Успешно сгенерирован Excel-файл общей статистики магазинов")
        return excel_file

    except Exception as e:
        logger.error(
            f"Ошибка при экспорте общей статистики магазинов "
            f"для администратора {current_user}: {e}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Не удалось сгенерировать файл статистики")

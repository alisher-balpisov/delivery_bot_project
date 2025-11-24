from typing import Any

from fastapi import APIRouter, HTTPException, Query, status

from backend.src.auth.dependencies import RequireAdmin
from backend.src.auth.service import mask_sensitive_data
from backend.src.common.constants import PaginatedResponse
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
    page: int = Query(1, ge=1, description="Номер страницы"),
    limit: int = Query(10, ge=1, le=100, description="Количество элементов на странице"),
    role: UserRole | None = None,
    is_used: bool | None = None,
):
    """
    Получить список кодов регистрации с пагинацией и фильтрацией.
    """
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
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    status: OrderStatus | None = Query(
        None, description="Фильтр по статусу: active, inactive или blocked"
    ),
    search: str | None = Query(None, description="Поиск по имени магазина или имени пользователя"),
):
    """
    Просмотреть все заказы системы (админ-панель).

    Примечание:
    - Этот эндпоинт предназначен для административного управления с текстовым поиском
    - Для получения истории заказов пользователя используйте GET /orders/history
    - Поддерживает поиск по названию магазина, имени курьера и описанию заказа
    """
    logger.info(
        f"Администратор {current_user} запрашивает список заказов: "
        f"{page=}, {limit=}, {status=}, {search=}"
    )

    try:
        result = await service.get_all_orders(
            db=db,
            page=page,
            limit=limit,
            status=status,
            search=search,
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
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
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

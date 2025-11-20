from typing import Any

from fastapi import APIRouter, HTTPException, Query, status

from backend.src.auth.dependencies import RequireAdmin
from backend.src.auth.service import mask_sensitive_data
from backend.src.common.constants import AllowedRoles, PaginatedResponse
from backend.src.common.enums import DisputeStatus, OrderStatus, UserRole, UserStatus
from backend.src.core.database import DbSession
from backend.src.core.logging import get_logger
from backend.src.couriers.schemas import CourierCardResponse
from backend.src.disputes.schemas import DisputeCardResponse
from backend.src.shops.schemas import ShopCardResponse

from . import service
from .schemas import RegistrationCodeResponse, SystemStatsResponse

logger = get_logger(__name__)


router = APIRouter()


@router.post(
    "/registration-codes",
    response_model=RegistrationCodeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_registration_code(
    role: AllowedRoles,
    current_user: RequireAdmin,
    db: DbSession,
):
    """
    Генерирует одноразовый код для регистрации пользователя определенной роли.
    Доступно только администраторам.
    """
    logger.info(f"Администратор {current_user} инициировал генерацию кода для роли {role.value}")
    try:
        new_code = await service.create_registration_code(
            db=db, role=role, created_by_admin_id=current_user.id
        )

        code = mask_sensitive_data(new_code.code)
        logger.info(
            f"Код регистрации {code} для роли {role.value} успешно сгенерирован "
            f"администратором {current_user}"
        )
        return new_code
    except RuntimeError as e:
        logger.error(
            f"Критическая ошибка при генерации кода для роли {role.value} "
            f"администратором {current_user}: {e}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера при генерации кода.")


@router.get(
    "/registration-codes",
    response_model=list[RegistrationCodeResponse],
    status_code=status.HTTP_200_OK,
)
async def get_registration_codes(
    current_user: RequireAdmin,
    db: DbSession,
    role: UserRole | None = None,
):
    """
    Получить все коды регистрации или коды для конкретной роли.
    Если параметр `role` не указан — возвращаются все коды.
    Доступно только администраторам.
    """
    try:
        if role:
            logger.info(
                f"Администратор ID {current_user.id} запрашивает коды регистрации для роли {role.value}"
            )
            codes = await service.get_registration_codes_by_role(db=db, role=role)
        else:
            logger.info(f"Администратор ID {current_user.id} запрашивает все коды регистрации")
            codes = await service.get_all_registration_codes(db=db)

        return codes

    except Exception as e:
        message = f"Ошибка при получении кодов регистрации для роли {role.value if role else 'всех ролей'}: {e}"
        logger.error(message, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Не удалось получить коды: {e!s}")


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
    "/couriers",
    response_model=PaginatedResponse[CourierCardResponse],
    status_code=status.HTTP_200_OK,
)
async def get_all_couriers(
    db: DbSession,
    current_user: RequireAdmin,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    status: UserStatus | None = Query(
        None, description="Фильтр по статусу: active, inactive или blocked"
    ),
    search: str | None = Query(None, description="Поиск по имени курьера или имени пользователя"),
):
    """
    Просмотреть всех курьеров.
    """
    logger.info(
        f"Администратор {current_user} запрашивает список курьеров: "
        f"{page=}, {limit=}, {status=}, {search=}"
    )

    try:
        result = await service.get_all_couriers(
            db=db,
            page=page,
            limit=limit,
            status=status,
            search=search,
        )

        logger.info(
            f"Успешно получен список курьеров: {len(result.items)} элементов на странице {page}"
        )
        return result

    except Exception as e:
        logger.error(
            f"Ошибка при получении списка курьеров для администратора {current_user}: {e}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Не удалось получить список курьеров")


@router.get(
    "/shops",
    response_model=PaginatedResponse[ShopCardResponse],
    status_code=status.HTTP_200_OK,
)
async def get_all_shops(
    db: DbSession,
    current_user: RequireAdmin,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    status: UserStatus | None = Query(
        None, description="Фильтр по статусу: active, inactive или blocked"
    ),
    search: str | None = Query(None, description="Поиск по имени магазина или имени пользователя"),
):
    """
    Просмотреть все магазины.
    """
    logger.info(
        f"Администратор {current_user} запрашивает список магазинов: "
        f"{page=}, {limit=}, {status=}, {search=}"
    )

    try:
        result = await service.get_all_shops(
            db=db,
            page=page,
            limit=limit,
            status=status,
            search=search,
        )

        logger.info(
            f"Успешно получен список магазинов: {len(result.items)} элементов на странице {page}"
        )
        return result

    except Exception as e:
        logger.error(
            f"Ошибка при получении списка магазинов для администратора {current_user}: {e}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Не удалось получить список магазинов")


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
    Просмотреть все текущие заказы.
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
    Просмотреть все текущие споры.
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

from typing import Any

from aiogram.filters import BaseFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, TelegramObject
from backend.src.common.enums import UserRole
from backend.src.core.logging import get_logger
from bot.clients.base_client import RequestResult
from bot.clients.users_client import UsersClient
from bot.dto import UserDTO
from bot.utils.helpers import parse_user_role

logger = get_logger(__name__)


class UserDataFilter(BaseFilter):
    """
    Фильтр-провайдер данных о пользователе.

    Ключевая роль этого фильтра — не просто разрешить или запретить доступ,
    а гарантированно предоставить объект `UserDTO` для каждого входящего
    события от пользователя. Он работает как "middleware" на уровне роутера.
    """

    async def __call__(
        self,
        event: TelegramObject,
        state: FSMContext,
        users_client: UsersClient,
    ) -> dict[str, UserDTO] | bool:
        """
        Основной метод. Пытается получить UserDTO из FSM, если не удается —
        восстанавливает из API. Возвращает словарь `{'user': user_dto}`.
        """
        if not isinstance(event, (Message, CallbackQuery)) or not event.from_user:
            return False

        telegram_id = event.from_user.id
        user_dto: UserDTO | None = None

        # 1. Попытка получить пользователя из кэша (FSM)
        state_data = await state.get_data()
        user_from_state = state_data.get("user")
        if isinstance(user_from_state, dict):
            if user_from_state.get("telegram_id") == telegram_id:
                user_dto = UserDTO.model_validate(user_from_state)
            else:
                logger.warning(
                    f"FSM data for user {user_from_state.get('telegram_id')} found "
                    f"for current user {telegram_id}. Discarding cached state."
                )

        # 2. Если в кэше нет или он невалиден, восстанавливаем из API
        if user_dto is None:
            user_dto = await self._restore_user_data(state, telegram_id, users_client)

        # 3. Возвращаем словарь, который aiogram добавит в аргументы хендлера
        return {"user": user_dto}

    async def _restore_user_data(
        self,
        state: FSMContext,
        telegram_id: int,
        users_client: UsersClient,
    ) -> UserDTO:
        """
        Запрашивает профиль пользователя через API и сохраняет его в FSM.
        Если пользователь не найден или произошла ошибка, создает "Гостя".
        """
        try:
            user_profile_result: RequestResult = await users_client.get_user_profile(telegram_id)

            if user_profile_result.success and isinstance(user_profile_result.data, dict):
                user_dto = self._user_dto_from_api_response(user_profile_result.data, telegram_id)
                await state.update_data(user=user_dto.model_dump())
                logger.info(
                    f"User data for {telegram_id} (Role: {user_dto.role.value}) restored from API and cached."
                )
                return user_dto

            logger.warning(
                f"Failed to restore profile for {telegram_id}. "
                f"Detail: {user_profile_result.detail}. Creating a temporary 'GUEST' profile."
            )
            return await self._create_guest_user(state, telegram_id)

        except Exception as e:
            logger.error(
                f"A critical error occurred while restoring data for {telegram_id}: {e}",
                exc_info=True,
            )
            return await self._create_guest_user(state, telegram_id)

    def _user_dto_from_api_response(self, api_data: dict[str, Any], telegram_id: int) -> UserDTO:
        """Безопасно создает UserDTO из ответа API."""
        return UserDTO(
            user_id=api_data.get("id"),
            telegram_id=api_data.get("telegram_id", telegram_id),
            name=api_data.get("name"),
            role=parse_user_role(api_data.get("role")),
        )

    async def _create_guest_user(self, state: FSMContext, telegram_id: int) -> UserDTO:
        """Создает DTO гостя и сохраняет его в FSM."""
        guest_dto = UserDTO(telegram_id=telegram_id, role=UserRole.GUEST)
        # Очищаем старые данные, чтобы не было конфликтов, и записываем гостя
        await state.set_data({"user": guest_dto.model_dump()})
        logger.info(f"Created and cached a 'GUEST' profile for {telegram_id}.")
        return guest_dto

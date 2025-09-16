from typing import Any

from aiogram.filters import BaseFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, TelegramObject, User
from backend.src.common.enums import UserRole
from backend.src.core.logging import get_logger
from bot.clients.base_client import RequestResult
from bot.clients.users_client import UsersClient
from bot.dto import UserDTO

logger = get_logger(__name__)


class UserDataFilter(BaseFilter):
    """
    Это фильтр, а не middleware. Он выполняется до хэндлеров и других фильтров.
    Его задача - вернуть словарь с ключом 'user', который будет добавлен в data.
    """

    async def __call__(
        self,
        event: TelegramObject,
        state: FSMContext,
        users_client: UsersClient,
    ) -> dict[str, Any]:  # Фильтр должен возвращать словарь
        from_user: User | None = None
        if isinstance(event, (Message, CallbackQuery)) and event.from_user:
            from_user = event.from_user

        # Если событие не от пользователя, возвращаем DTO по умолчанию
        if not from_user:
            return {"user": UserDTO(telegram_id=0, role=UserRole.GUEST)}

        telegram_id = from_user.id
        user_dto: UserDTO | None = None

        state_data = await state.get_data()
        user_from_state = state_data.get("user")
        if user_from_state and isinstance(user_from_state, dict):
            user_dto = UserDTO.model_validate(user_from_state)
            if user_dto.telegram_id != telegram_id:
                user_dto = None

        if not user_dto:
            user_dto = await self._restore_user_data(state, telegram_id, users_client)

        # --- КЛЮЧЕВОЕ ИЗМЕНЕНИЕ ---
        # Возвращаем словарь. Aiogram смерджит его с основным data.
        return {"user": user_dto}

    async def _restore_user_data(
        self,
        state: FSMContext,
        telegram_id: int,
        users_client: UsersClient,
    ) -> UserDTO:
        # Этот метод остается без изменений
        try:
            user_profile_result: RequestResult = await users_client.get_user_profile(telegram_id)
            if user_profile_result.success and isinstance(user_profile_result.data, dict):
                user_profile = user_profile_result.data
                user_dto = UserDTO(
                    user_id=user_profile.get("id"),
                    telegram_id=user_profile.get("telegram_id", telegram_id),
                    name=user_profile.get("name"),
                    role=UserRole(user_profile.get("role", UserRole.GUEST.value)),
                )
                await state.update_data(user=user_dto.model_dump())
                logger.info(f"Восстановлены данные для пользователя {telegram_id} из API")
                return user_dto
            else:
                logger.warning(
                    f"Не удалось восстановить профиль для {telegram_id}. Детали: {user_profile_result.detail}"
                )
                guest_dto = UserDTO(telegram_id=telegram_id, role=UserRole.GUEST)
                await state.update_data(user=guest_dto.model_dump())
                return guest_dto
        except Exception as e:
            logger.error(
                f"Критическая ошибка восстановления данных пользователя {telegram_id}: {e}"
            )
            guest_dto = UserDTO(telegram_id=telegram_id, role=UserRole.GUEST)
            await state.update_data(user=guest_dto.model_dump())
            return guest_dto

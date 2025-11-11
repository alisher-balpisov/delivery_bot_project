from typing import Any

from aiogram.filters import BaseFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, TelegramObject
from backend.src.common.enums import UserRole
from backend.src.core.logging import get_logger
from bot.clients.auth_client import AuthClient
from bot.clients.users_client import UsersClient
from bot.dto import UserDTO
from bot.utils.helpers import parse_user_role

logger = get_logger(__name__)


class UserDataFilter(BaseFilter):
    """
    Фильтр-провайдер, который обеспечивает наличие UserDTO и JWT токена
    для каждого входящего события.
    """

    async def __call__(
        self,
        event: TelegramObject,
        state: FSMContext,
        auth_client: AuthClient,
        users_client: UsersClient,
    ) -> dict[str, Any] | bool:
        """
        Основной метод.
        1. Проверяет наличие токена в FSM.
        2. Если токен есть, получает профиль пользователя.
        3. Если токена нет (или он невалиден), запрашивает новый.
        4. Если ничего не помогает, создает DTO гостя.
        """
        if not isinstance(event, (Message, CallbackQuery)) or not event.from_user:
            return False

        telegram_id = event.from_user.id

        state_data = await state.get_data()
        token = state_data.get("jwt_token")

        user_dto: UserDTO | None = None

        # 1. Попытка получить пользователя по существующему токену
        if token:
            profile_result = await users_client.get_user_profile(token)
            if profile_result.success and isinstance(profile_result.data, dict):
                user_dto = self._user_dto_from_api_response(profile_result.data)

        # 2. Если токена нет или он невалиден, запрашиваем новый
        if user_dto is None:
            token_result = await auth_client.login(telegram_id)
            if token_result.success and isinstance(token_result.data, dict):
                new_token = token_result.data.get("access_token")
                await state.update_data(jwt_token=new_token)
                logger.info(f"JWT токен для пользователя {telegram_id} обновлен и кэширован")

                # Получаем профиль с новым токеном
                profile_result = await users_client.get_user_profile(new_token)
                if profile_result.success and isinstance(profile_result.data, dict):
                    user_dto = self._user_dto_from_api_response(profile_result.data)

        # 3. Если ничего не помогло, создаем гостя
        if user_dto is None:
            user_dto = await self._create_guest_user(state, telegram_id)

        # Сохраняем актуальный DTO в FSM
        await state.update_data(user=user_dto.model_dump())

        # 4. Возвращаем словарь, который aiogram добавит в аргументы хендлера
        return {"user": user_dto}

    def _user_dto_from_api_response(self, api_data: dict[str, Any]) -> UserDTO:
        """Безопасно создает UserDTO из ответа API."""
        return UserDTO(
            user_id=api_data.get("id"),
            telegram_id=api_data.get("telegram_id"),
            name=api_data.get("name"),
            role=parse_user_role(api_data.get("role")),
        )

    async def _create_guest_user(self, state: FSMContext, telegram_id: int) -> UserDTO:
        """Создает DTO гостя и очищает старые данные."""
        guest_dto = UserDTO(telegram_id=telegram_id, role=UserRole.GUEST)
        # Очищаем старые данные, чтобы не было конфликтов, и записываем гостя
        await state.set_data({"user": guest_dto.model_dump()})
        logger.info(f"Создан и кэширован профиль 'ГОСТЬ' для {telegram_id}.")
        return guest_dto

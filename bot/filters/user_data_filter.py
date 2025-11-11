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
    Фильтр-провайдер, который обеспечивает наличие UserDTO для каждого входящего события.

    Логика работы:
    1. Проверяет наличие токена в FSM
    2. Если токен есть и валиден - получает профиль пользователя
    3. Если токена нет - пытается получить через login()
    4. Если login() не удался - создает DTO гостя
    """

    async def __call__(
        self,
        event: TelegramObject,
        state: FSMContext,
        auth_client: AuthClient,
        users_client: UsersClient,
    ) -> dict[str, Any] | bool:
        """
        Основной метод фильтра.
        Возвращает словарь с user (UserDTO) для использования в хендлерах.
        """
        if not isinstance(event, (Message, CallbackQuery)) or not event.from_user:
            return False

        telegram_id = event.from_user.id
        state_data = await state.get_data()
        token = state_data.get("jwt_token")

        user_dto: UserDTO | None = None

        # 1. Попытка получить пользователя по существующему токену
        if token:
            user_dto = await self._get_user_by_token(token, users_client, telegram_id)

            # Если токен валиден, возвращаем пользователя
            if user_dto:
                await state.update_data(user=user_dto.model_dump())
                return {"user": user_dto}

        # 2. Токена нет или он невалиден - пытаемся получить новый через login()
        logger.debug(f"Попытка получить новый токен для пользователя {telegram_id}")
        token_result = await auth_client.login(telegram_id)

        if token_result.success and isinstance(token_result.data, dict):
            new_token = token_result.data.get("access_token")

            if new_token:
                await state.update_data(jwt_token=new_token)
                logger.info(f"JWT токен для пользователя {telegram_id} обновлен и кэширован")

                # Получаем профиль с новым токеном
                user_dto = await self._get_user_by_token(new_token, users_client, telegram_id)

                if user_dto:
                    await state.update_data(user=user_dto.model_dump())
                    return {"user": user_dto}

        # 3. Не удалось получить токен - определяем статус по коду ответа
        status_code = token_result.status_code

        # 403 означает, что пользователь существует, но регистрация не завершена
        if status_code == 403:
            logger.info(f"Пользователь {telegram_id} не завершил регистрацию (403)")
            user_dto = UserDTO(telegram_id=telegram_id, role=UserRole.GUEST)

        # 401 или любой другой код - пользователь не найден или ошибка
        else:
            logger.info(
                f"Пользователь {telegram_id} не найден или ошибка авторизации (код: {status_code})"
            )
            user_dto = UserDTO(telegram_id=telegram_id, role=UserRole.GUEST)

        # Сохраняем гостя в FSM
        await state.update_data(user=user_dto.model_dump())
        return {"user": user_dto}

    async def _get_user_by_token(
        self, token: str, users_client: UsersClient, telegram_id: int
    ) -> UserDTO | None:
        """
        Получает профиль пользователя по токену и создает UserDTO.
        Возвращает None если токен невалиден или произошла ошибка.
        """
        try:
            profile_result = await users_client.get_user_profile(token)

            if profile_result.success and isinstance(profile_result.data, dict):
                api_data = profile_result.data
                return self._user_dto_from_api_response(api_data)

            # Токен невалиден или ошибка API
            logger.warning(
                f"Не удалось получить профиль для {telegram_id}: "
                f"{profile_result.status_code} - {profile_result.detail}"
            )
            return None

        except Exception as e:
            logger.error(f"Ошибка при получении профиля для {telegram_id}: {e}", exc_info=True)
            return None

    def _user_dto_from_api_response(self, api_data: dict[str, Any]) -> UserDTO:
        """Безопасно создает UserDTO из ответа API."""
        return UserDTO(
            user_id=api_data.get("id"),
            telegram_id=api_data.get("telegram_id"),
            name=api_data.get("name"),
            role=parse_user_role(api_data.get("role")),
        )

from backend.src.core.logging import get_logger

from .base_client import BaseApiClient, RequestResult

logger = get_logger(__name__)


class AuthClient(BaseApiClient):
    async def login(self, telegram_id: int) -> RequestResult:
        """
        Получает JWT токен для пользователя по его telegram_id.

        Этот эндпоинт используется для входа существующих зарегистрированных пользователей.

        Returns:
            RequestResult с:
            - success=True и data={'access_token': ..., 'user': {...}} при успехе (200)
            - success=False и status_code=401 если пользователь не найден
            - success=False и status_code=403 если регистрация не завершена
            - success=False и status_code=423 если аккаунт заблокирован
        """
        logger.debug(f"Запрос токена для telegram_id={telegram_id}")

        return await self._make_request(
            "POST",
            "/auth/login",
            json_data={"telegram_id": telegram_id},
            expected_status=200,
        )

    async def register_guest(self, telegram_id: int, username: str | None = None) -> RequestResult:
        """
        Регистрирует пользователя как гостя (создает в БД).
        """
        logger.debug(f"Регистрация гостя telegram_id={telegram_id}")
        return await self._make_request(
            "POST",
            "/auth/register-guest",
            json_data={"telegram_id": telegram_id, "username": username},
            expected_status=200,
        )

    async def auth_by_code(
        self,
        telegram_id: int,
        code: str,
        username: str | None = None,
    ) -> RequestResult:
        """
        Отправляет код для аутентификации и получения JWT токена.

        Этот эндпоинт используется для регистрации новых пользователей
        или повторного входа уже зарегистрированных.

        Returns:
            RequestResult с:
            - success=True и data={'access_token': ..., 'user': {...}} при успехе
            - success=False с деталями ошибки при неудаче
        """
        logger.debug(f"Аутентификация по коду для telegram_id={telegram_id}")

        return await self._make_request(
            "POST",
            "/auth/by-code",
            json_data={"telegram_id": telegram_id, "code": code, "username": username},
            expected_status=200,
        )

    async def refresh_token(self, refresh_token: str) -> RequestResult:
        """
        Обновляет access token используя refresh token.

        Args:
            refresh_token: Существующий refresh token

        Returns:
            RequestResult с новыми токенами при успехе:
            - access_token
            - refresh_token (может быть новый)
            - expires_in
            - refresh_expires_in
        """
        logger.debug("Запрос на обновление токена")

        return await self._make_request(
            "POST",
            "/auth/refresh",
            json_data={"refresh_token": refresh_token},
            expected_status=200,
        )

    async def logout(self, access_token: str) -> RequestResult:
        """
        Выход пользователя (инвалидация токенов на сервере).

        Args:
            access_token: Access токен пользователя

        Returns:
            RequestResult с успехом при выходе
        """
        logger.debug("Запрос на выход пользователя")

        return await self._make_request(
            "POST",
            "/auth/logout",
            token=access_token,
            expected_status=200,
        )

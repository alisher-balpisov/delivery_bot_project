from fastapi import HTTPException, status


class UserNotFoundException(HTTPException):
    def __init__(self, user_id: int | None = None, telegram_id: int | None = None):
        if user_id:
            detail = f"Пользователь с ID {user_id} не найден"
        elif telegram_id:
            detail = f"Пользователь с Telegram ID {telegram_id} не найден"
        else:
            detail = "Пользователь не найден"

        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail,
        )

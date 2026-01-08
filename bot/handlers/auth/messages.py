# messages.py — Тексты ошибок входа и сообщений авторизации
# Этот файл реэкспортирует сообщения из bot/messages.py (если нужно)
# и может содержать локальные сообщения, специфичные только для auth handlers

from bot.messages import AuthMessages, AuthServiceMessages

# Реэкспорт для удобства импорта внутри модуля
__all__ = [
    "AuthMessages",
    "AuthServiceMessages",
]

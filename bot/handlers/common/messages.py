# messages.py — Общие сообщения
# Этот файл реэкспортирует сообщения из bot/messages.py
# и может содержать локальные сообщения, специфичные только для common handlers

from bot.messages import CommonMessages, CommonServiceMessages

__all__ = [
    "CommonMessages",
    "CommonServiceMessages",
]

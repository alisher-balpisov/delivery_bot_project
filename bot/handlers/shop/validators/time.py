"""Валидатор времени доставки."""

from datetime import datetime, timedelta


def validate_delivery_time(time_text: str) -> tuple[datetime | None, str | None]:
    """
    Валидирует время доставки.

    Поддерживаемые форматы:
    - HH:MM (сегодня в указанное время)
    - DD.MM HH:MM
    - DD.MM.YYYY HH:MM

    Args:
        time_text: Текст с временем от пользователя

    Returns:
        Tuple(datetime или None, сообщение об ошибке или None)
    """
    now = datetime.now()
    time_text = time_text.strip()

    formats = [
        ("%H:%M", lambda dt: dt.replace(year=now.year, month=now.month, day=now.day)),
        ("%d.%m %H:%M", lambda dt: dt.replace(year=now.year)),
        ("%d.%m.%Y %H:%M", lambda dt: dt),
    ]

    for fmt, adjuster in formats:
        try:
            parsed = datetime.strptime(time_text, fmt)
            delivery_time = adjuster(parsed)

            # Проверяем, что время в будущем
            if delivery_time <= now:
                # Если указано только время и оно уже прошло - добавляем день
                if fmt == "%H:%M":
                    delivery_time += timedelta(days=1)
                else:
                    return None, "Время доставки должно быть в будущем"

            # Проверяем максимальный горизонт планирования (7 дней)
            max_date = now + timedelta(days=7)
            if delivery_time > max_date:
                return None, "Нельзя планировать доставку более чем на 7 дней вперёд"

            return delivery_time, None

        except ValueError:
            continue

    return None, (
        "Неверный формат времени. Используйте:\n"
        "• <code>HH:MM</code> - сегодня в указанное время\n"
        "• <code>ДД.ММ HH:MM</code> - конкретная дата и время\n"
        "• <code>ДД.ММ.ГГГГ HH:MM</code> - полная дата и время"
    )

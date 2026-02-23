"""Валидатор цены заказа."""

MIN_ORDER_PRICE = 3000
MAX_ORDER_PRICE = 50000


def validate_price(price_text: str) -> tuple[int | None, str | None]:
    """
    Валидирует цену заказа.

    Args:
        price_text: Текст с ценой от пользователя

    Returns:
        Tuple(цена в int или None, сообщение об ошибке или None)
    """
    if not price_text:
        return None, "Пожалуйста, введите цену"

    try:
        cleaned = price_text.strip().replace(" ", "").replace(",", "")

        if not cleaned.isdigit():
            return None, "Цена должна содержать только цифры"

        price = int(cleaned)

        if price <= 0:
            return None, "Цена должна быть больше нуля"

        if price < MIN_ORDER_PRICE:
            return None, f"Минимальная цена заказа: {MIN_ORDER_PRICE:,} ₸"

        if price > MAX_ORDER_PRICE:
            return None, f"Максимальная цена заказа: {MAX_ORDER_PRICE:,} ₸"

        return price, None

    except (ValueError, TypeError, ArithmeticError):
        return None, "Неверный формат цены. Введите только число."

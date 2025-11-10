from fastapi import HTTPException, status


class OrderException(HTTPException):
    """
    Базовое исключение для всех ошибок, связанных с заказами.

    Все остальные исключения модуля наследуются от него
    для удобной обработки в exception handlers.
    """

    def __init__(self, status_code: int, detail: str):
        super().__init__(status_code=status_code, detail=detail)


class OrderNotFoundException(OrderException):
    """
    Исключение для случаев, когда заказ не найден в БД.

    Args:
        order_id: ID ненайденного заказа
    """

    def __init__(self, order_id: int):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Заказ с ID {order_id} не найден",
        )


class OrderUpdateForbiddenException(OrderException):
    """
    Исключение для случаев, когда у пользователя нет прав на изменение заказа.

    Может возникать по причинам:
    - Пользователь не владелец заказа (для магазинов/курьеров)
    - Попытка изменить запрещённые поля
    - Попытка изменить заказ в финальном статусе
    - Попытка установить недопустимый статус

    Args:
        detail: Описание причины отказа (по умолчанию: общее сообщение)
    """

    def __init__(self, detail: str = "У вас нет прав на изменение этого заказа"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )


class OrderAccessForbiddenException(OrderException):
    """
    Исключение для случаев, когда у пользователя нет прав на просмотр заказа.

    Может возникать по причинам:
    - Магазин пытается просмотреть чужой заказ
    - Курьер пытается просмотреть не назначенный ему заказ
    - Отсутствует профиль магазина/курьера

    Args:
        detail: Описание причины отказа (по умолчанию: общее сообщение)
    """

    def __init__(self, detail: str = "У вас нет прав на доступ к этому заказу"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )


class OrderInvalidStatusTransitionException(OrderException):
    """
    Исключение для недопустимых переходов между статусами заказа.

    Например:
    - Попытка завершить заказ, который еще не в доставке
    - Попытка отменить уже завершённый заказ

    Args:
        current_status: Текущий статус заказа
        attempted_status: Статус, на который пытались перейти
    """

    def __init__(self, current_status: str, attempted_status: str):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Невозможно изменить статус с '{current_status}' на '{attempted_status}'",
        )


class CourierNotActiveException(OrderException):
    """
    Исключение для случаев, когда курьер неактивен.

    Возникает при попытке назначить неактивного курьера на заказ.

    Args:
        courier_id: ID неактивного курьера
    """

    def __init__(self, courier_id: int):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Курьер с ID {courier_id} неактивен и не может принимать заказы",
        )


class OrderValidationException(OrderException):
    """
    Исключение для ошибок валидации данных заказа.

    Используется для бизнес-правил, не покрытых Pydantic валидацией.

    Args:
        detail: Описание ошибки валидации
    """

    def __init__(self, detail: str):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        )

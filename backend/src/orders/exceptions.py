from fastapi import HTTPException, status


class OrderException(HTTPException):
    """Базовое исключение для ошибок, связанных с заказами."""

    def __init__(self, status_code: int, detail: str):
        super().__init__(status_code=status_code, detail=detail)


class OrderNotFoundException(OrderException):
    """Исключение для случаев, когда заказ не найден."""

    def __init__(self, order_id: int):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Заказ с ID {order_id} не найден",
        )


class OrderUpdateForbiddenException(OrderException):
    """Исключение для случаев, когда у пользователя нет прав на обновление заказа."""

    def __init__(self, detail: str = "У вас нет прав на изменение этого заказа"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )


class OrderAccessForbiddenException(OrderException):
    """Исключение для случаев, когда у пользователя нет прав на доступ к заказу."""

    def __init__(self, detail: str = "У вас нет прав на доступ к этому заказу"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )

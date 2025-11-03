from fastapi import HTTPException, status

NO_ACCESS_EXCEPTION = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="Нет доступа к этому заказу",
)

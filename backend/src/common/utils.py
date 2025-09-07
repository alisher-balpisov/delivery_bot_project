from typing import Annotated

from pydantic import PlainValidator


def validate_phone(v):
    if not isinstance(v, str):
        raise ValueError("Телефон должен быть строкой")
    if not v.startswith("+"):
        raise ValueError("Телефон должен начинаться с +")
    return v


Phone = Annotated[str, PlainValidator(validate_phone)]

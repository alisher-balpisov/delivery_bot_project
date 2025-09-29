from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, text
from sqlalchemy.orm import Mapped, mapped_column


class CreatedAtMixin:
    """Mixin для поля created_at."""

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class UpdatedAtMixin:
    """Mixin для поля updated_at."""

    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class TimestampMixin(CreatedAtMixin, UpdatedAtMixin):
    """Mixin для полей created_at и updated_at."""

    pass


class SoftDeleteMixin:
    """Mixin для мягкого удаления (is_deleted) и соответствующего критерия загрузки."""

    is_deleted: Mapped[bool] = mapped_column(
        default=False, server_default=text("false"), index=True
    )

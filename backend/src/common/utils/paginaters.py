from collections.abc import Sequence
from typing import Any

from sqlalchemy import ColumnElement, Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute
from sqlalchemy.orm.interfaces import ORMOption


def _validate_pagination_params(page: int, limit: int) -> None:
    """Валидация параметров пагинации."""
    if page < 1 or limit < 1:
        raise ValueError("Page and limit must be greater than zero.")

    if limit > 100:
        raise ValueError("Limit cannot exceed 100")


def _validate_search_term(search: str) -> None:
    """Валидация строки поиска."""
    if len(search) > 100:
        raise ValueError("Search term too long (max 100 characters)")


def _escape_like_pattern(search: str) -> str:
    """Экранирование специальных символов LIKE и подготовка паттерна."""
    search_escaped = search.replace("%", r"\%").replace("_", r"\_")
    return f"%{search_escaped.lower()}%"


def _build_status_filter(
    model: type,
    status: Any,
    status_field: str = "status",
) -> ColumnElement[bool] | None:
    """Создает фильтр по статусу."""
    status_attr = getattr(model, status_field, None)
    if status_attr is None:
        return None
    return status_attr == status


def _build_search_filter(
    search: str,
    search_fields: list[InstrumentedAttribute],
) -> ColumnElement[bool]:
    """Создает фильтр поиска по нескольким полям."""
    _validate_search_term(search)
    search_term = _escape_like_pattern(search)

    search_conditions = [field.ilike(search_term) for field in search_fields]
    return or_(*search_conditions)


def _build_filters(
    model: type,
    status: Any | None = None,
    status_field: str = "status",
    search: str | None = None,
    search_fields: list[InstrumentedAttribute] | None = None,
) -> list[ColumnElement[bool]] | None:
    """Собирает и возвращает список фильтров для запроса."""
    filters = []

    if status is not None:
        status_filter = _build_status_filter(model, status, status_field)
        if status_filter is not None:
            filters.append(status_filter)

    if search and search_fields:
        search_filter = _build_search_filter(search, search_fields)
        filters.append(search_filter)

    return filters if filters else None


def _apply_joins(
    query: Select,
    joins: Sequence[tuple[type, ColumnElement[bool]] | tuple[type, ColumnElement[bool], bool]]
    | None,
) -> Select:
    """Применяет JOIN'ы к запросу."""
    if not joins:
        return query

    for join_item in joins:
        if len(join_item) == 3:
            join_model, join_condition, isouter = join_item  # type: ignore
            query = query.join(join_model, join_condition, isouter=isouter)
        else:
            join_model, join_condition = join_item  # type: ignore
            query = query.join(join_model, join_condition)

    return query


def _apply_eager_loading(
    query: Select,
    eager_load_options: list[ORMOption] | None,
) -> Select:
    """Применяет опции eager loading к запросу."""
    if not eager_load_options:
        return query

    for option in eager_load_options:
        query = query.options(option)

    return query


def _apply_sorting(
    query: Select,
    model: type,
    sort_by_field: str,
    sort_desc: bool,
) -> Select:
    """Применяет сортировку к запросу."""
    if not hasattr(model, sort_by_field):
        return query

    order_field = getattr(model, sort_by_field)
    return query.order_by(order_field.desc() if sort_desc else order_field)


def _apply_pagination(
    query: Select,
    page: int,
    limit: int,
) -> Select:
    """Применяет offset и limit для пагинации."""
    offset = (page - 1) * limit
    return query.offset(offset).limit(limit)


async def _get_total_count(
    db: AsyncSession,
    model: type,
    filters: list[ColumnElement[bool]] | None,
    joins: Sequence[tuple[type, ColumnElement[bool]] | tuple[type, ColumnElement[bool], bool]]
    | None,
    apply_joins: bool = True,
) -> int:
    """Получает общее количество записей с учетом фильтров."""
    count_query = select(func.count()).select_from(model)
    if apply_joins:
        count_query = _apply_joins(count_query, joins)

    if filters:
        count_query = count_query.where(*filters)

    total = await db.scalar(count_query)
    return total or 0


async def _get_paginated_items[ModelType](
    db: AsyncSession,
    model: type[ModelType],
    page: int,
    limit: int,
    filters: list[ColumnElement[bool]] | None,
    joins: Sequence[tuple[type, ColumnElement[bool]] | tuple[type, ColumnElement[bool], bool]]
    | None,
    eager_load_options: list[ORMOption] | None,
    sort_by_field: str,
    sort_desc: bool,
) -> list[ModelType]:
    """Получает пагинированный список элементов."""
    data_query = select(model)
    data_query = _apply_joins(data_query, joins)
    data_query = _apply_eager_loading(data_query, eager_load_options)

    if filters:
        data_query = data_query.where(*filters)

    data_query = _apply_sorting(data_query, model, sort_by_field, sort_desc)
    data_query = _apply_pagination(data_query, page, limit)

    result = await db.execute(data_query)
    return list(result.scalars().all())


async def get_paginated_list[ModelType](
    db: AsyncSession,
    model: type[ModelType],
    page: int,
    limit: int,
    status: Any | None = None,
    status_field: str = "status",
    status_model: type | None = None,
    search: str | None = None,
    search_fields: list[InstrumentedAttribute] | None = None,
    joins: Sequence[tuple[type, ColumnElement[bool]] | tuple[type, ColumnElement[bool], bool]]
    | None = None,
    eager_load_options: list[ORMOption] | None = None,
    sort_by_field: str = "id",
    sort_desc: bool = False,
    additional_filters: list[ColumnElement[bool]] | None = None,
) -> tuple[int, list[ModelType]]:
    """
    Универсальная функция для получения пагинированного списка сущностей.

    Args:
        db: Сессия базы данных
        model: Модель для запроса
        page: Номер страницы
        limit: Количество элементов на странице
        status: Значение статуса для фильтрации
        status_field: Имя поля статуса (по умолчанию "status")
        status_model: Модель, в которой искать поле статуса (если None, используется model)
        search: Строка поиска
        search_fields: Поля для поиска
        joins: Список кортежей (модель, условие) для JOIN'ов
        eager_load_options: Опции для загрузки связанных объектов
        sort_by_field: Поле для сортировки
        sort_desc: Сортировать по убыванию
        additional_filters: Дополнительные фильтры SQLAlchemy (optional)
    """
    _validate_pagination_params(page, limit)

    filter_model = status_model if status_model else model
    filters = _build_filters(
        model=filter_model,
        status=status,
        status_field=status_field,
        search=search,
        search_fields=search_fields,
    )

    if filters is None:
        filters = []

    if additional_filters:
        filters.extend(additional_filters)

    is_external_status_filter = (
        status is not None and status_model is not None and status_model is not model
    )

    apply_joins_for_count = bool((search and search_fields) or is_external_status_filter)
    total = await _get_total_count(db, model, filters, joins, apply_joins=apply_joins_for_count)

    if not total:
        return 0, []

    items = await _get_paginated_items(
        db=db,
        model=model,
        page=page,
        limit=limit,
        filters=filters,
        joins=joins,
        eager_load_options=eager_load_options,
        sort_by_field=sort_by_field,
        sort_desc=sort_desc,
    )

    return total, items

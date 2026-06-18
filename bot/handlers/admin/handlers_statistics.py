from datetime import datetime, timedelta

from aiogram import F, Router
from aiogram.types import BufferedInputFile, CallbackQuery
from backend.src.common.enums import UserRole
from backend.src.core.logging import get_logger
from backend.src.couriers.schemas import CourierListItem

from bot.clients.admin_client import AdminClient
from bot.clients.couriers_client import CouriersClient
from bot.clients.shops_client import ShopsClient
from bot.dto import UserDTO
from bot.filters.filters import RoleFilter
from bot.keyboards.admin import (
    StatsCallback,
    StatsType,
    get_export_loading_keyboard,
    get_period_selection_keyboard,
    get_statistics_main_menu,
    get_stats_type_keyboard,
)
from bot.keyboards.couriers import (
    CourierFilter,
    CouriersCallback,
    get_couriers_list_for_stats_keyboard,
)
from bot.keyboards.shops import ShopFilter, ShopsCallback, get_shops_list_for_stats_keyboard
from bot.utils.token_manager import TokenManager

logger = get_logger(__name__)

router = Router(name="admin_statistics_handlers")
router.message.filter(RoleFilter(UserRole.ADMIN))
router.callback_query.filter(RoleFilter(UserRole.ADMIN))


# ==================== Главное меню ====================


@router.callback_query(F.data == "show_statistics_admin")
async def show_statistics_menu(callback: CallbackQuery):
    """Главное меню статистики."""
    text = "📊 <b>Экспорт статистики</b>\n\nВыберите тип отчета, который хотите сгенерировать:"

    keyboard = get_statistics_main_menu()
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(StatsCallback.filter(F.action == "menu"))
async def back_to_stats_menu(callback: CallbackQuery):
    """Возврат в главное меню статистики."""
    await show_statistics_menu(callback)


# ==================== Выбор магазина ====================


@router.callback_query(StatsCallback.filter(F.action == "select_shop"))
async def select_shop_for_stats(
    callback: CallbackQuery, token_manager: TokenManager, shops_client: ShopsClient, user: UserDTO
):
    """Выбор магазина для экспорта статистики."""
    token = await token_manager.get_token(user.telegram_id)

    try:
        result = await shops_client.get_shops(token=token, page=1, limit=10)

        keyboard = get_shops_list_for_stats_keyboard(
            shops=result.items,
            page=1,
            total_pages=result.pages,
            current_filter=ShopFilter.ALL,
        )

        text = "🏪 <b>Выберите магазин</b>\n\nДля какого магазина экспортировать статистику?"

        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка при загрузке магазинов: {e}", exc_info=True)
        await callback.answer("Ошибка при загрузке списка магазинов", show_alert=True)


@router.callback_query(ShopsCallback.filter(F.action == "stats_list"))
async def stats_shops_pagination(
    callback: CallbackQuery,
    callback_data: ShopsCallback,
    token_manager: TokenManager,
    shops_client: ShopsClient,
    user: UserDTO,
):
    """Пагинация и фильтрация списка магазинов в режиме статистики."""
    token = await token_manager.get_token(user.telegram_id)

    try:
        await callback.answer()

        status = (
            None if callback_data.filter_type == ShopFilter.ALL else callback_data.filter_type.value
        )

        result = await shops_client.get_shops(
            token=token, page=callback_data.page, limit=10, status=status
        )

        keyboard = get_shops_list_for_stats_keyboard(
            shops=result.items,
            page=callback_data.page,
            total_pages=result.pages,
            current_filter=callback_data.filter_type,
        )

        text = "🏪 <b>Выберите магазин</b>\n\nДля какого магазина экспортировать статистику?"

        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Ошибка при загрузке магазинов: {e}", exc_info=True)
        await callback.answer("Ошибка при загрузке списка магазинов", show_alert=True)


@router.callback_query(ShopsCallback.filter(F.action == "stats_select_shop"))
async def shop_selected_for_stats(callback: CallbackQuery, callback_data: ShopsCallback):
    """Магазин выбран — переход к выбору типа статистики."""
    shop_id = callback_data.shop_id

    text = (
        f"📊 <b>Статистика магазина #{shop_id}</b>\n\n"
        "Выберите тип отчета:\n\n"
        "📋 <b>Базовая</b> - основная информация по заказам\n"
        "📊 <b>Расширенная</b> - детальная финансовая информация"
    )

    keyboard = get_stats_type_keyboard(entity_type="shop", entity_id=shop_id)

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


# ==================== Выбор курьера ====================


@router.callback_query(StatsCallback.filter(F.action == "select_courier"))
async def select_courier_for_stats(
    callback: CallbackQuery,
    token_manager: TokenManager,
    couriers_client: CouriersClient,
    user: UserDTO,
):
    """Выбор курьера для экспорта статистики."""
    token = await token_manager.get_token(user.telegram_id)

    try:
        result = await couriers_client.get_couriers(token=token, page=1, size=10)

        if not result.success:
            await callback.answer("Ошибка при загрузке списка курьеров", show_alert=True)
            return

        data = result.data
        items_raw = data.get("items", [])
        total = data.get("total", 0)

        items = [CourierListItem.model_validate(item) for item in items_raw]

        # Используем специализированную клавиатуру для статистики
        keyboard = get_couriers_list_for_stats_keyboard(
            couriers=items,
            page=1,
            total_pages=max(1, (total + 9) // 10),
            current_filter=CourierFilter.ALL,
        )

        text = "🚴 <b>Выберите курьера</b>\n\nДля какого курьера экспортировать статистику?"

        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка при загрузке курьеров: {e}", exc_info=True)
        await callback.answer("Ошибка при загрузке списка курьеров", show_alert=True)


@router.callback_query(CouriersCallback.filter(F.action == "stats_list_couriers"))
async def stats_couriers_pagination(
    callback: CallbackQuery,
    callback_data: CouriersCallback,
    token_manager: TokenManager,
    couriers_client: CouriersClient,
    user: UserDTO,
):
    """Пагинация и фильтрация списка курьеров в режиме статистики."""
    token = await token_manager.get_token(user.telegram_id)

    try:
        await callback.answer()

        # Маппинг фильтра
        filter_params = {}
        if callback_data.filter_type != CourierFilter.ALL:
            if callback_data.filter_type == CourierFilter.ACTIVE:
                filter_params["is_active"] = True
            elif callback_data.filter_type == CourierFilter.INACTIVE:
                filter_params["is_active"] = False
            elif callback_data.filter_type == CourierFilter.ON_SHIFT:
                filter_params["on_shift"] = True

        result = await couriers_client.get_couriers(
            token=token, page=callback_data.page, size=10, **filter_params
        )

        if not result.success:
            await callback.answer("Ошибка при загрузке курьеров", show_alert=True)
            return

        data = result.data
        items_raw = data.get("items", [])
        total = data.get("total", 0)

        items = [CourierListItem.model_validate(item) for item in items_raw]

        keyboard = get_couriers_list_for_stats_keyboard(
            couriers=items,
            page=callback_data.page,
            total_pages=max(1, (total + 9) // 10),
            current_filter=callback_data.filter_type,
        )

        text = "🚴 <b>Выберите курьера</b>\n\nДля какого курьера экспортировать статистику?"

        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Ошибка при загрузке курьеров: {e}", exc_info=True)
        await callback.answer("Ошибка при загрузке курьеров", show_alert=True)


@router.callback_query(CouriersCallback.filter(F.action == "stats_select_courier"))
async def courier_selected_for_stats(callback: CallbackQuery, callback_data: CouriersCallback):
    """Курьер выбран — переход к выбору типа статистики."""
    courier_id = callback_data.courier_id

    text = (
        f"📊 <b>Статистика курьера #{courier_id}</b>\n\n"
        "Выберите тип отчета:\n\n"
        "📋 <b>Базовая</b> - заказы и заработок\n"
        "📊 <b>Расширенная</b> - полная финансовая информация"
    )

    keyboard = get_stats_type_keyboard(entity_type="courier", entity_id=courier_id)

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


# ==================== Выбор типа и периода ====================


@router.callback_query(StatsCallback.filter(F.action == "select_type"))
async def back_to_select_type(callback: CallbackQuery, callback_data: StatsCallback):
    """Возврат к выбору типа статистики (кнопка Назад из выбора периода)."""
    entity_type = callback_data.entity_type
    entity_id = callback_data.entity_id

    if entity_type == "shop":
        text = (
            f"📊 <b>Статистика магазина #{entity_id}</b>\n\n"
            "Выберите тип отчета:\n\n"
            "📋 <b>Базовая</b> - основная информация по заказам\n"
            "📊 <b>Расширенная</b> - детальная финансовая информация"
        )
    elif entity_type == "courier":
        text = (
            f"📊 <b>Статистика курьера #{entity_id}</b>\n\n"
            "Выберите тип отчета:\n\n"
            "📋 <b>Базовая</b> - заказы и заработок\n"
            "📊 <b>Расширенная</b> - полная финансовая информация"
        )
    else:
        # Для "all" — возвращаемся в главное меню статистики
        await show_statistics_menu(callback)
        return

    keyboard = get_stats_type_keyboard(entity_type=entity_type, entity_id=entity_id)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(StatsCallback.filter(F.action == "select_period"))
async def select_period_for_stats(callback: CallbackQuery, callback_data: StatsCallback):
    """Выбор периода для статистики."""
    entity_name = {"shop": "магазина", "courier": "курьера", "all": "всех магазинов"}.get(
        callback_data.entity_type, ""
    )

    stats_name = "Базовая" if callback_data.stats_type == StatsType.COMMON else "Расширенная"

    text = (
        f"📅 <b>Выбор периода</b>\n\n"
        f"Тип отчета: {stats_name}\n"
        f"Для: {entity_name}\n\n"
        "Выберите период для экспорта:"
    )

    keyboard = get_period_selection_keyboard(
        entity_type=callback_data.entity_type,
        entity_id=callback_data.entity_id,
        stats_type=callback_data.stats_type,
    )

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


# ==================== Экспорт ====================


@router.callback_query(StatsCallback.filter(F.action == "export_quick"))
async def export_quick_period(
    callback: CallbackQuery,
    callback_data: StatsCallback,
    token_manager: TokenManager,
    admin_client: AdminClient,
    user: UserDTO,
):
    """Экспорт за быстрый период (сегодня, неделя, месяц)."""
    days = callback_data.page  # 0=today, 7=week, 30=month

    date_to = datetime.now()
    if days == 0:
        date_from = date_to.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        date_from = date_to - timedelta(days=days)

    await _perform_export(
        callback=callback,
        callback_data=callback_data,
        token_manager=token_manager,
        admin_client=admin_client,
        user=user,
        date_from=date_from,
        date_to=date_to,
        from_last_payment=False,
    )


@router.callback_query(StatsCallback.filter(F.action == "export_from_last"))
async def export_from_last_payment(
    callback: CallbackQuery,
    callback_data: StatsCallback,
    token_manager: TokenManager,
    admin_client: AdminClient,
    user: UserDTO,
):
    """Экспорт с последней инкассации/выплаты.

    date_from устанавливается на минимально возможную дату (1 января 2020),
    так как реальная дата будет определена на бэкенде при from_last_payment=True.
    """
    date_to = datetime.now()
    # Минимальная дата — бэкенд переопределит при from_last_payment=True
    date_from = datetime(2020, 1, 1)

    await _perform_export(
        callback=callback,
        callback_data=callback_data,
        token_manager=token_manager,
        admin_client=admin_client,
        user=user,
        date_from=date_from,
        date_to=date_to,
        from_last_payment=True,
    )


@router.callback_query(StatsCallback.filter(F.action == "export_all"))
async def export_all_shops(
    callback: CallbackQuery, token_manager: TokenManager, admin_client: AdminClient, user: UserDTO
):
    """Экспорт общей статистики всех магазинов — переход к выбору периода."""
    text = (
        "📅 <b>Выбор периода</b>\n\n"
        "Тип отчета: Общая статистика всех магазинов\n\n"
        "Выберите период для экспорта:"
    )

    keyboard = get_period_selection_keyboard(
        entity_type="all",
        entity_id=None,
        stats_type=StatsType.ADVANCED,
    )

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


# ==================== Общая логика экспорта ====================


async def _perform_export(
    callback: CallbackQuery,
    callback_data: StatsCallback,
    token_manager: TokenManager,
    admin_client: AdminClient,
    user: UserDTO,
    date_from: datetime,
    date_to: datetime,
    from_last_payment: bool,
) -> None:
    """Общая логика экспорта статистики.

    Отправляет запрос на бэкенд, получает Excel-файл и отправляет
    его пользователю через Telegram.
    """
    # Показываем индикатор загрузки
    loading_text = "⏳ <b>Генерация отчета...</b>\n\nПожалуйста, подождите."
    keyboard = get_export_loading_keyboard()

    try:
        await callback.message.edit_text(loading_text, reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:
        logger.debug("Не удалось обновить сообщение загрузки экспорта: %s", e)

    await callback.answer("Генерация файла...", cache_time=0)

    token = await token_manager.get_token(user.telegram_id)

    try:
        # Выбираем метод API в зависимости от типа сущности
        if callback_data.entity_type == "shop":
            result = await admin_client.export_shop_statistics(
                token=token,
                shop_id=callback_data.entity_id,
                date_from=date_from,
                date_to=date_to,
                stats_type=callback_data.stats_type.value,
                from_last_payment=from_last_payment,
            )
        elif callback_data.entity_type == "courier":
            result = await admin_client.export_courier_statistics(
                token=token,
                courier_id=callback_data.entity_id,
                date_from=date_from,
                date_to=date_to,
                stats_type=callback_data.stats_type.value,
                from_last_payout=from_last_payment,
            )
        elif callback_data.entity_type == "all":
            result = await admin_client.export_all_shops_statistics(
                token=token, date_from=date_from, date_to=date_to
            )
        else:
            await callback.message.edit_text(
                "❌ Неизвестный тип экспорта", reply_markup=get_statistics_main_menu()
            )
            return

        if not result.success:
            error_detail = result.detail or "Неизвестная ошибка"
            error_text = f"❌ <b>Ошибка при генерации отчета</b>\n\n{error_detail}"
            await callback.message.edit_text(
                error_text, reply_markup=get_statistics_main_menu(), parse_mode="HTML"
            )
            return

        # Формируем имя файла и отправляем
        filename = (
            f"statistics_{callback_data.entity_type}"
            f"_{date_from.strftime('%Y%m%d')}_{date_to.strftime('%Y%m%d')}.xlsx"
        )

        await callback.message.answer_document(
            document=BufferedInputFile(result.data, filename=filename),
            caption=(
                f"✅ <b>Отчет готов</b>\n\n"
                f"Период: {date_from.strftime('%Y-%m-%d')} — {date_to.strftime('%Y-%m-%d')}"
            ),
            parse_mode="HTML",
        )

        # Возвращаемся в меню статистики
        await callback.message.edit_text(
            "✅ Файл отправлен!", reply_markup=get_statistics_main_menu()
        )

    except Exception as e:
        logger.error(f"Ошибка при экспорте статистики: {e}", exc_info=True)
        await callback.message.edit_text(
            "❌ <b>Произошла ошибка при генерации отчета</b>\n\n"
            "Попробуйте позже или обратитесь к разработчику.",
            reply_markup=get_statistics_main_menu(),
            parse_mode="HTML",
        )

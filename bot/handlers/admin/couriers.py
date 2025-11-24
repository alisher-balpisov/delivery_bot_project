from aiogram import F, Router
from aiogram.types import CallbackQuery
from backend.src.common.enums import UserRole
from backend.src.core.logging import get_logger
from bot.clients.couriers_client import CouriersClient
from bot.dto import UserDTO
from bot.filters.filters import RoleFilter
from bot.keyboards.couriers import (
    CourierFilter,
    CouriersCallback,
    get_courier_card_keyboard,
    get_couriers_list_keyboard,
)
from bot.utils.token_manager import TokenManager

logger = get_logger(__name__)

router = Router(name="admin_couriers_handlers")
router.message.filter(RoleFilter(UserRole.ADMIN))
router.callback_query.filter(RoleFilter(UserRole.ADMIN))


@router.callback_query(F.data == "show_couriers")
async def show_couriers_handler(
    callback: CallbackQuery,
    token_manager: TokenManager,
    couriers_client: CouriersClient,
    user: UserDTO,
):
    """
    Показать список курьеров (первая страница, активные).
    """
    await list_couriers(
        callback=callback,
        token_manager=token_manager,
        couriers_client=couriers_client,
        user=user,
        page=1,
        filter_val=CourierFilter.ACTIVE,
    )


@router.callback_query(CouriersCallback.filter(F.action == "list"))
async def list_couriers_callback(
    callback: CallbackQuery,
    callback_data: CouriersCallback,
    token_manager: TokenManager,
    couriers_client: CouriersClient,
    user: UserDTO,
):
    """
    Обработка пагинации и фильтрации списка курьеров.
    """
    await list_couriers(
        callback=callback,
        token_manager=token_manager,
        couriers_client=couriers_client,
        user=user,
        page=callback_data.page,
        filter_val=callback_data.filter_type,
    )


async def list_couriers(
    callback: CallbackQuery,
    token_manager: TokenManager,
    couriers_client: CouriersClient,
    user: UserDTO,
    page: int,
    filter_val: CourierFilter,
):
    """
    Общая логика получения и отображения списка курьеров.
    """
    token = await token_manager.get_token(user.telegram_id)

    # Маппинг фильтра UI на параметры API
    api_status = None
    if filter_val == CourierFilter.ACTIVE:
        api_status = "active"
    elif filter_val == CourierFilter.INACTIVE:
        api_status = "inactive"
    elif filter_val == CourierFilter.ON_SHIFT:
        api_status = "on_shift"
    # ALL -> None

    result = await couriers_client.get_couriers(
        token=token,
        page=page,
        size=10,
        status=api_status,
    )

    if not result.success:
        await callback.answer("Ошибка при загрузке списка курьеров", show_alert=True)
        return

    data = result.data
    items = data.get("items", [])
    total = data.get("total", 0)
    size = data.get("size", 10)

    # Конвертируем dict в объекты (так как Pydantic модели не всегда доступны/удобны здесь)
    # Но лучше использовать валидацию. В данном случае items - это список dict.
    # Для клавиатуры нам нужны объекты с атрибутами.
    # Создадим простой класс-обертку или используем SimpleNamespace
    from types import SimpleNamespace

    courier_objects = []
    for item in items:
        courier_objects.append(SimpleNamespace(**item))

    total_pages = (total + size - 1) // size if size > 0 else 1

    keyboard = get_couriers_list_keyboard(
        couriers=courier_objects,
        page=page,
        total_pages=total_pages,
        current_filter=filter_val,
    )

    text = f"📋 <b>Список курьеров</b>\nВсего: {total}"

    # Если это новое сообщение или редактирование
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")

    await callback.answer()


@router.callback_query(CouriersCallback.filter(F.action == "open"))
async def open_courier_card(
    callback: CallbackQuery,
    callback_data: CouriersCallback,
    token_manager: TokenManager,
    couriers_client: CouriersClient,
    user: UserDTO,
):
    """
    Открыть карточку курьера.
    """
    token = await token_manager.get_token(user.telegram_id)
    courier_id = callback_data.courier_id

    result = await couriers_client.get_courier_details(token, courier_id)

    if not result.success:
        await callback.answer("Не удалось загрузить данные курьера", show_alert=True)
        return

    courier = result.data
    # Формируем текст карточки
    # Предполагаем поля: full_name, username, phone_numbers, is_active, rating

    full_name = courier.get("full_name", "Не указано")
    username = courier.get("username")
    username_text = f"@{username}" if username else "Нет"
    phones = ", ".join(courier.get("phone_numbers", [])) or "Нет"
    rating = courier.get("rating")
    rating_text = f"{rating:.1f} ⭐️" if rating else "Нет оценок"

    status_emoji = "🟢 На смене" if courier.get("is_active") else "🔴 Не на смене"
    user_status = courier.get("status", "unknown")

    text = (
        f"👤 <b>Курьер: {full_name}</b>\n\n"
        f"📱 Телеграм: {username_text}\n"
        f"📞 Телефон: {phones}\n"
        f"⭐️ Рейтинг: {rating_text}\n"
        f"🔄 Статус смены: {status_emoji}\n"
        f"🔒 Статус аккаунта: {user_status}\n"
    )

    keyboard = get_courier_card_keyboard(
        page=callback_data.page,
        current_filter=callback_data.filter_type,
    )

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

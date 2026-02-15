"""Обработчики списка споров."""

from aiogram.types import CallbackQuery
from backend.src.common.enums import UserRole

from bot.clients.auth_client import AuthClient
from bot.clients.disputes_client import DisputesClient
from bot.filters.filters import RoleFilter
from bot.handlers.shop.orders.callbacks import DisputesListCallback
from bot.handlers.shop.orders.dispute.keyboards import get_disputes_list_keyboard
from bot.handlers.shop.orders.dispute.router import router
from bot.redis_storage import UserDataStorage
from bot.utils.api_helper import execute_api_call
from bot.utils.token_manager import TokenManager


@router.callback_query(DisputesListCallback.filter(), RoleFilter(UserRole.SHOP))
async def dispute_list_pagination_handler(
    callback: CallbackQuery,
    auth_client: AuthClient,
    disputes_client: DisputesClient,
    user_storage: UserDataStorage,
    callback_data: DisputesListCallback,
):
    """Обработка пагинации списка споров."""
    await dispute_list_handler(
        callback, auth_client, disputes_client, user_storage, page=callback_data.page
    )


async def dispute_list_handler(
    callback: CallbackQuery,
    auth_client: AuthClient,
    disputes_client: DisputesClient,
    user_storage: UserDataStorage,
    page: int = 1,
):
    """Отображение списка споров."""
    token_manager = TokenManager(auth_client, user_storage)

    result = await execute_api_call(
        token_manager,
        callback.from_user.id,
        disputes_client.get_my_disputes,
        page=page,
        limit=10,
    )

    if not result.success or not result.data:
        await callback.answer("Не удалось загрузить список споров", show_alert=True)
        return

    data = result.data
    items = data.get("items", [])
    total = data.get("total", 0)
    total_pages = data.get("pages", 1)

    if not items:
        await callback.answer("У вас пока нет споров", show_alert=True)
        return

    text = (
        f"<b>🗂 Список ваших споров</b>\n\n"
        f"Всего найдено: {total}\n"
        f"Выберите спор для просмотра деталей:"
    )

    keyboard = get_disputes_list_keyboard(
        disputes=items,
        page=page,
        total_pages=total_pages,
    )

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

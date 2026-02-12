"""Обработчики подтверждения и создания заказа."""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from backend.src.common.enums import UserRole

from bot.clients.auth_client import AuthClient
from bot.clients.orders_client import OrdersClient
from bot.filters.filters import RoleFilter
from bot.handlers.shop.keyboards.create_order import get_confirmation_keyboard
from bot.handlers.shop.keyboards.main import get_back_to_menu_keyboard
from bot.handlers.shop.services.order_service import OrderCreationService
from bot.redis_storage import UserDataStorage
from bot.utils.token_manager import TokenManager

router = Router(name="order_create_confirm")


@router.callback_query(F.data == "order_confirm", RoleFilter(UserRole.SHOP))
async def confirm_and_create_order(
    callback: CallbackQuery,
    state: FSMContext,
    orders_client: OrdersClient,
    auth_client: AuthClient,
    user_storage: UserDataStorage,
):
    """Подтверждение и создание заказа через API."""
    data = await state.get_data()

    # Проверка обязательных данных
    if not data.get("description"):
        await callback.answer("⚠️ Недостаточно данных для создания заказа", show_alert=True)
        return

    # Получаем токен
    telegram_id = callback.from_user.id
    token_manager = TokenManager(auth_client, user_storage)
    token = await token_manager.get_token(telegram_id)

    if not token:
        await callback.answer("⚠️ Ошибка авторизации. Попробуйте перезайти.", show_alert=True)
        return

    # Показываем индикатор загрузки
    await callback.answer("⏳ Создаём заказ...")

    # Создаём заказ через сервис
    success, message = await OrderCreationService.create_order(
        token=token,
        order_details=data,
        orders_client=orders_client,
    )

    if success:
        await state.clear()
        await callback.message.edit_text(
            text=message, reply_markup=get_back_to_menu_keyboard(), parse_mode="HTML"
        )
    else:
        await callback.message.edit_text(
            text=message,
            reply_markup=get_confirmation_keyboard(),
            parse_mode="HTML",
        )


@router.callback_query(F.data == "order_cancel", RoleFilter(UserRole.SHOP))
async def cancel_order_creation(callback: CallbackQuery, state: FSMContext):
    """Отменить создание заказа."""
    await state.clear()

    await callback.message.edit_text(
        text="❌ <b>Создание заказа отменено</b>\n\n<i>Вы можете создать новый заказ в любое время.</i>",
        reply_markup=get_back_to_menu_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer("Заказ отменён")

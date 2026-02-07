# handlers.py — Меню магазина, профиль
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from backend.src.common.enums import UserRole

from bot.clients.auth_client import AuthClient
from bot.clients.shops_client import ShopsClient
from bot.filters.filters import RoleFilter
from bot.handlers.shop.keyboards import get_shop_main_menu_keyboard
from bot.handlers.shop.messages import ShopMessages, ShopProfileMessages
from bot.handlers.shop.states import EditProfileStates
from bot.redis_storage import UserDataStorage
from bot.utils.token_manager import TokenManager

router = Router(name="shop_main_handlers")


@router.message(Command("start"), RoleFilter(UserRole.SHOP))
async def shop_main_menu_handler(
    message: Message,
    state: FSMContext,
    auth_client: AuthClient,
    shops_client: ShopsClient,
    user_storage: UserDataStorage,
):
    """Главное меню магазина."""
    await state.clear()

    token_manager = TokenManager(auth_client, user_storage)
    token = await token_manager.get_token(message.from_user.id)

    stats = await shops_client.get_shop_stats(token)

    text = ShopMessages.MAIN_MENU.format(
        active_orders=stats.active_orders,
        today_orders=stats.orders_today,
        active_disputes=stats.active_disputes,
    )

    await message.answer(text, reply_markup=get_shop_main_menu_keyboard())


@router.callback_query(F.data == "shop_main_menu", RoleFilter(UserRole.SHOP))
async def shop_main_menu_callback_handler(
    callback: CallbackQuery,
    state: FSMContext,
    auth_client: AuthClient,
    shops_client: ShopsClient,
    user_storage: UserDataStorage,
):
    """Возврат в главное меню магазина (через inline-кнопку)."""
    await state.clear()

    token_manager = TokenManager(auth_client, user_storage)
    token = await token_manager.get_token(callback.from_user.id)

    stats = await shops_client.get_shop_stats(token)

    text = ShopMessages.MAIN_MENU.format(
        active_orders=stats.active_orders,
        today_orders=stats.orders_today,
        active_disputes=stats.active_disputes,
    )

    await callback.message.edit_text(text, reply_markup=get_shop_main_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "show_statistics", RoleFilter(UserRole.SHOP))
async def show_statistics_handler(
    callback: CallbackQuery,
    auth_client: AuthClient,
    shops_client: ShopsClient,
    user_storage: UserDataStorage,
):
    """Показать статистику магазина."""
    token_manager = TokenManager(auth_client, user_storage)
    token = await token_manager.get_token(callback.from_user.id)

    stats = await shops_client.get_shop_stats(token)

    text = (
        "📊 <b>Статистика магазина</b>\n\n"
        f"📦 Активные заказы: {stats.active_orders}\n"
        f"📅 Заказов сегодня: {stats.orders_today}\n"
        f"⚠️ Активные споры: {stats.active_disputes}\n"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="shop_main_menu")]]
    )
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "edit_profile", RoleFilter(UserRole.SHOP))
async def edit_profile_handler(callback: CallbackQuery, state: FSMContext):
    """Показать меню редактирования профиля магазина."""
    await state.clear()

    text = "⚙️ <b>Редактирование профиля</b>\n\nВыберите, что хотите изменить:"

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📝 Название магазина", callback_data="edit_shop_name")],
            [InlineKeyboardButton(text="📍 Адрес", callback_data="edit_shop_address")],
            [InlineKeyboardButton(text="📞 Телефон", callback_data="edit_shop_phone")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="shop_main_menu")],
        ]
    )
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


# =============================================================================
# Редактирование названия магазина
# =============================================================================


@router.callback_query(F.data == "edit_shop_name", RoleFilter(UserRole.SHOP))
async def edit_shop_name_start(callback: CallbackQuery, state: FSMContext):
    """Начать редактирование названия магазина."""

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="edit_profile")],
        ]
    )

    await callback.message.edit_text(
        ShopProfileMessages.REQUEST_NAME, reply_markup=keyboard, parse_mode="HTML"
    )
    await state.set_state(EditProfileStates.waiting_for_name)
    await callback.answer()


@router.message(EditProfileStates.waiting_for_name, RoleFilter(UserRole.SHOP))
async def edit_shop_name_process(
    message: Message,
    state: FSMContext,
    auth_client: AuthClient,
    shops_client: ShopsClient,
    user_storage: UserDataStorage,
):
    """Обработать новое название магазина."""

    new_name = message.text.strip() if message.text else ""

    # Валидация
    if len(new_name) < 3:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отмена", callback_data="edit_profile")],
            ]
        )
        await message.answer(
            ShopProfileMessages.ERROR_NAME_TOO_SHORT, reply_markup=keyboard, parse_mode="HTML"
        )
        return

    if len(new_name) > 100:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отмена", callback_data="edit_profile")],
            ]
        )
        await message.answer(
            ShopProfileMessages.ERROR_NAME_TOO_LONG, reply_markup=keyboard, parse_mode="HTML"
        )
        return

    # Обновление через API
    try:
        token_manager = TokenManager(auth_client, user_storage)
        token = await token_manager.get_token(message.from_user.id)

        await shops_client.update_shop_profile(token, {"name": new_name})

        # Обновляем кеш профиля
        cached_profile = await user_storage.get_cached_profile(message.from_user.id)
        if cached_profile:
            cached_profile["name"] = new_name
            await user_storage.cache_profile(message.from_user.id, cached_profile)

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад в меню", callback_data="edit_profile")],
            ]
        )

        await message.answer(
            ShopProfileMessages.SUCCESS_UPDATE.format(field="Название магазина", value=new_name),
            reply_markup=keyboard,
            parse_mode="HTML",
        )
        await state.clear()

    except Exception as e:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="edit_shop_name")],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="edit_profile")],
            ]
        )
        await message.answer(
            ShopProfileMessages.ERROR_API.format(error=str(e)),
            reply_markup=keyboard,
            parse_mode="HTML",
        )
        await state.clear()


# =============================================================================
# Редактирование адреса магазина
# =============================================================================


@router.callback_query(F.data == "edit_shop_address", RoleFilter(UserRole.SHOP))
async def edit_shop_address_start(callback: CallbackQuery, state: FSMContext):
    """Начать редактирование адреса магазина."""

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="edit_profile")],
        ]
    )

    await callback.message.edit_text(
        ShopProfileMessages.REQUEST_ADDRESS, reply_markup=keyboard, parse_mode="HTML"
    )
    await state.set_state(EditProfileStates.waiting_for_address)
    await callback.answer()


@router.message(EditProfileStates.waiting_for_address, RoleFilter(UserRole.SHOP))
async def edit_shop_address_process(
    message: Message,
    state: FSMContext,
    auth_client: AuthClient,
    shops_client: ShopsClient,
    user_storage: UserDataStorage,
):
    """Обработать новый адрес магазина."""

    new_address = message.text.strip() if message.text else ""

    # Валидация
    if len(new_address) < 10:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отмена", callback_data="edit_profile")],
            ]
        )
        await message.answer(
            ShopProfileMessages.ERROR_ADDRESS_TOO_SHORT, reply_markup=keyboard, parse_mode="HTML"
        )
        return

    if len(new_address) > 200:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отмена", callback_data="edit_profile")],
            ]
        )
        await message.answer(
            ShopProfileMessages.ERROR_ADDRESS_TOO_LONG, reply_markup=keyboard, parse_mode="HTML"
        )
        return

    # Обновление через API
    try:
        token_manager = TokenManager(auth_client, user_storage)
        token = await token_manager.get_token(message.from_user.id)

        await shops_client.update_shop_profile(token, {"address": new_address})

        # Обновляем кеш профиля
        cached_profile = await user_storage.get_cached_profile(message.from_user.id)
        if cached_profile:
            cached_profile["address"] = new_address
            await user_storage.cache_profile(message.from_user.id, cached_profile)

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад в меню", callback_data="edit_profile")],
            ]
        )

        await message.answer(
            ShopProfileMessages.SUCCESS_UPDATE.format(field="Адрес магазина", value=new_address),
            reply_markup=keyboard,
            parse_mode="HTML",
        )
        await state.clear()

    except Exception as e:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔄 Попробовать снова", callback_data="edit_shop_address"
                    )
                ],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="edit_profile")],
            ]
        )
        await message.answer(
            ShopProfileMessages.ERROR_API.format(error=str(e)),
            reply_markup=keyboard,
            parse_mode="HTML",
        )
        await state.clear()


# =============================================================================
# Редактирование телефона магазина
# =============================================================================


@router.callback_query(F.data == "edit_shop_phone", RoleFilter(UserRole.SHOP))
async def edit_shop_phone_start(callback: CallbackQuery, state: FSMContext):
    """Начать редактирование телефона магазина."""

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="edit_profile")],
        ]
    )

    await callback.message.edit_text(
        ShopProfileMessages.REQUEST_PHONE, reply_markup=keyboard, parse_mode="HTML"
    )
    await state.set_state(EditProfileStates.waiting_for_phone)
    await callback.answer()


@router.message(EditProfileStates.waiting_for_phone, RoleFilter(UserRole.SHOP))
async def edit_shop_phone_process(
    message: Message,
    state: FSMContext,
    auth_client: AuthClient,
    shops_client: ShopsClient,
    user_storage: UserDataStorage,
):
    """Обработать новый телефон магазина."""
    import re

    phone_input = message.text.strip() if message.text else ""

    # Нормализация: удаляем все кроме цифр и +
    normalized_phone = re.sub(r"[^\d+]", "", phone_input)

    # Валидация: должно быть от 10 до 20 цифр
    digits_only = re.sub(r"[^\d]", "", normalized_phone)

    if len(digits_only) < 10 or len(digits_only) > 20:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отмена", callback_data="edit_profile")],
            ]
        )
        await message.answer(
            ShopProfileMessages.ERROR_PHONE_INVALID, reply_markup=keyboard, parse_mode="HTML"
        )
        return

    # Обновление через API
    try:
        token_manager = TokenManager(auth_client, user_storage)
        token = await token_manager.get_token(message.from_user.id)

        await shops_client.update_shop_profile(token, {"phone_number": [normalized_phone]})

        # Обновляем кеш профиля
        cached_profile = await user_storage.get_cached_profile(message.from_user.id)
        if cached_profile:
            cached_profile["phone_numbers"] = [normalized_phone]
            await user_storage.cache_profile(message.from_user.id, cached_profile)

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад в меню", callback_data="edit_profile")],
            ]
        )

        await message.answer(
            ShopProfileMessages.SUCCESS_UPDATE.format(
                field="Номер телефона", value=normalized_phone
            ),
            reply_markup=keyboard,
            parse_mode="HTML",
        )
        await state.clear()

    except Exception as e:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔄 Попробовать снова", callback_data="edit_shop_phone"
                    )
                ],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="edit_profile")],
            ]
        )
        await message.answer(
            ShopProfileMessages.ERROR_API.format(error=str(e)),
            reply_markup=keyboard,
            parse_mode="HTML",
        )
        await state.clear()

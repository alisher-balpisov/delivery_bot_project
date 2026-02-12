"""Обработчики редактирования профиля магазина."""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from backend.src.common.enums import UserRole

from bot.clients.auth_client import AuthClient
from bot.clients.shops_client import ShopsClient
from bot.filters.filters import RoleFilter
from bot.handlers.shop.keyboards.main import get_profile_edit_keyboard
from bot.handlers.shop.messages import ProfileMessages
from bot.handlers.shop.states import ProfileEditStates
from bot.handlers.shop.validators.profile import (
    validate_phone_number,
    validate_shop_address,
    validate_shop_name,
)
from bot.redis_storage import UserDataStorage
from bot.utils.token_manager import TokenManager

router = Router(name="shop_profile")


@router.callback_query(F.data == "edit_profile", RoleFilter(UserRole.SHOP))
async def edit_profile_menu_handler(callback: CallbackQuery, state: FSMContext):
    """Меню редактирования профиля."""
    await state.clear()

    text = "⚙️ <b>Редактирование профиля</b>\n\nВыберите, что хотите изменить:"
    keyboard = get_profile_edit_keyboard()

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


# =============================================================================
# Редактирование названия
# =============================================================================


@router.callback_query(F.data == "edit_shop_name", RoleFilter(UserRole.SHOP))
async def edit_name_start(callback: CallbackQuery, state: FSMContext):
    """Начать изменение названия."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="edit_profile")]]
    )

    await callback.message.edit_text(
        ProfileMessages.REQUEST_NAME, reply_markup=keyboard, parse_mode="HTML"
    )
    await state.set_state(ProfileEditStates.waiting_for_name)
    await callback.answer()


@router.message(ProfileEditStates.waiting_for_name, RoleFilter(UserRole.SHOP))
async def edit_name_process(
    message: Message,
    state: FSMContext,
    auth_client: AuthClient,
    shops_client: ShopsClient,
    user_storage: UserDataStorage,
):
    """Обработать новое название."""
    new_name = message.text.strip() if message.text else ""

    # Валидация
    is_valid, error = validate_shop_name(new_name)
    if not is_valid:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="edit_profile")]]
        )
        await message.answer(f"❌ {error}", reply_markup=keyboard, parse_mode="HTML")
        return

    # Обновление через API
    try:
        token_manager = TokenManager(auth_client, user_storage)
        token = await token_manager.get_token(message.from_user.id)

        await shops_client.update_shop_profile(token, {"name": new_name})

        # Обновляем кеш
        cached_profile = await user_storage.get_cached_profile(message.from_user.id)
        if cached_profile:
            cached_profile["name"] = new_name
            await user_storage.cache_profile(message.from_user.id, cached_profile)

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад в меню", callback_data="edit_profile")]
            ]
        )

        await message.answer(
            ProfileMessages.SUCCESS_UPDATE.format(field="Название магазина", value=new_name),
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
            ProfileMessages.ERROR_API.format(error=str(e)),
            reply_markup=keyboard,
            parse_mode="HTML",
        )
        await state.clear()


# =============================================================================
# Редактирование адреса
# =============================================================================


@router.callback_query(F.data == "edit_shop_address", RoleFilter(UserRole.SHOP))
async def edit_address_start(callback: CallbackQuery, state: FSMContext):
    """Начать изменение адреса."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="edit_profile")]]
    )

    await callback.message.edit_text(
        ProfileMessages.REQUEST_ADDRESS, reply_markup=keyboard, parse_mode="HTML"
    )
    await state.set_state(ProfileEditStates.waiting_for_address)
    await callback.answer()


@router.message(ProfileEditStates.waiting_for_address, RoleFilter(UserRole.SHOP))
async def edit_address_process(
    message: Message,
    state: FSMContext,
    auth_client: AuthClient,
    shops_client: ShopsClient,
    user_storage: UserDataStorage,
):
    """Обработать новый адрес."""
    new_address = message.text.strip() if message.text else ""

    # Валидация
    is_valid, error = validate_shop_address(new_address)
    if not is_valid:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="edit_profile")]]
        )
        await message.answer(f"❌ {error}", reply_markup=keyboard, parse_mode="HTML")
        return

    # Обновление через API
    try:
        token_manager = TokenManager(auth_client, user_storage)
        token = await token_manager.get_token(message.from_user.id)

        await shops_client.update_shop_profile(token, {"address": new_address})

        # Обновляем кеш
        cached_profile = await user_storage.get_cached_profile(message.from_user.id)
        if cached_profile:
            cached_profile["address"] = new_address
            await user_storage.cache_profile(message.from_user.id, cached_profile)

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад в меню", callback_data="edit_profile")]
            ]
        )

        await message.answer(
            ProfileMessages.SUCCESS_UPDATE.format(field="Адрес магазина", value=new_address),
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
            ProfileMessages.ERROR_API.format(error=str(e)),
            reply_markup=keyboard,
            parse_mode="HTML",
        )
        await state.clear()


# =============================================================================
# Редактирование телефона
# =============================================================================


@router.callback_query(F.data == "edit_shop_phone", RoleFilter(UserRole.SHOP))
async def edit_phone_start(callback: CallbackQuery, state: FSMContext):
    """Начать изменение телефона."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="edit_profile")]]
    )

    await callback.message.edit_text(
        ProfileMessages.REQUEST_PHONE, reply_markup=keyboard, parse_mode="HTML"
    )
    await state.set_state(ProfileEditStates.waiting_for_phone)
    await callback.answer()


@router.message(ProfileEditStates.waiting_for_phone, RoleFilter(UserRole.SHOP))
async def edit_phone_process(
    message: Message,
    state: FSMContext,
    auth_client: AuthClient,
    shops_client: ShopsClient,
    user_storage: UserDataStorage,
):
    """Обработать новый телефон."""
    phone_input = message.text.strip() if message.text else ""

    # Валидация и нормализация
    normalized_phone, error = validate_phone_number(phone_input)
    if error:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="edit_profile")]]
        )
        await message.answer(f"❌ {error}", reply_markup=keyboard, parse_mode="HTML")
        return

    # Обновление через API
    try:
        token_manager = TokenManager(auth_client, user_storage)
        token = await token_manager.get_token(message.from_user.id)

        await shops_client.update_shop_profile(token, {"phone_number": [normalized_phone]})

        # Обновляем кеш
        cached_profile = await user_storage.get_cached_profile(message.from_user.id)
        if cached_profile:
            cached_profile["phone_numbers"] = [normalized_phone]
            await user_storage.cache_profile(message.from_user.id, cached_profile)

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад в меню", callback_data="edit_profile")]
            ]
        )

        await message.answer(
            ProfileMessages.SUCCESS_UPDATE.format(field="Номер телефона", value=normalized_phone),
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
            ProfileMessages.ERROR_API.format(error=str(e)),
            reply_markup=keyboard,
            parse_mode="HTML",
        )
        await state.clear()

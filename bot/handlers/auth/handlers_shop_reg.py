from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from backend.src.core.logging import get_logger

from bot.clients import AdminClient, UsersClient
from bot.clients.shops_client import ShopsClient
from bot.handlers.common.handlers import handle_authorized_user
from bot.messages import AuthMessages
from bot.states import RegistrationStates
from bot.utils.token_manager import TokenManager, UserDataStorage

logger = get_logger(__name__)

router = Router(name="shop_registration")


@router.message(RegistrationStates.waiting_for_shop_name)
async def shop_name_handler(message: Message, state: FSMContext) -> None:
    """Обрабатывает ввод названия магазина."""
    name = (message.text or "").strip()
    if not name:
        await message.answer("❌ Название магазина не может быть пустым. Попробуйте еще раз:")
        return

    await state.update_data(shop_name=name)
    await state.set_state(RegistrationStates.waiting_for_shop_address)
    await message.answer("📍 Введите адрес магазина:")


@router.message(RegistrationStates.waiting_for_shop_address)
async def shop_address_handler(message: Message, state: FSMContext) -> None:
    """Обрабатывает ввод адреса магазина."""
    address = (message.text or "").strip()
    if not address:
        await message.answer("❌ Адрес не может быть пустым. Попробуйте еще раз:")
        return

    await state.update_data(shop_address=address)
    await state.set_state(RegistrationStates.waiting_for_shop_address_link)
    await message.answer("🔗 Введите ссылку на адрес (например, Google Maps или 2GIS):")


@router.message(RegistrationStates.waiting_for_shop_address_link)
async def shop_address_link_handler(message: Message, state: FSMContext) -> None:
    """Обрабатывает ввод ссылки на адрес."""
    link = (message.text or "").strip()
    if not link:
        await message.answer("❌ Ссылка не может быть пустой. Попробуйте еще раз:")
        return

    await state.update_data(shop_address_link=link)
    await state.set_state(RegistrationStates.waiting_for_shop_phone)
    await message.answer("📱 Введите номера телефонов магазина (можно несколько через запятую):")


@router.message(RegistrationStates.waiting_for_shop_phone)
async def shop_phone_handler(
    message: Message,
    state: FSMContext,
    shops_client: ShopsClient,
    token_manager: TokenManager,
    users_client: UsersClient,
    user_storage: UserDataStorage,
    admin_client: AdminClient,
) -> None:
    """Обрабатывает ввод телефонов и завершает регистрацию."""
    phones_text = (message.text or "").strip()
    if not phones_text:
        await message.answer("❌ Номера телефонов не могут быть пустыми. Попробуйте еще раз:")
        return

    phones = [p.strip() for p in phones_text.split(",") if p.strip()]

    if not phones:
        await message.answer("❌ Введите хотя бы один номер телефона.")
        return

    data = await state.get_data()
    shop_update_data = {
        "name": data.get("shop_name"),
        "address": data.get("shop_address"),
        "address_link": data.get("shop_address_link"),
        "phone_number": phones,
    }

    try:
        token = await token_manager.get_token(message.from_user.id)
        if not token:
            await message.answer(AuthMessages.AUTH_ERROR)
            await state.clear()
            return

        await shops_client.update_shop_profile(token, shop_update_data)

        await message.answer(
            "✅ Регистрация магазина успешно завершена!\n\n"
            f"Название: {shop_update_data['name']}\n"
            f"Адрес: {shop_update_data['address']}\n"
            f"Телефоны: {', '.join(phones)}\n\n"
            "Теперь вы можете пользоваться ботом."
        )

        await state.clear()
        await user_storage.delete_user_data(message.from_user.id)

        await handle_authorized_user(
            message,
            users_client,
            user_storage,
            message.from_user.id,
            token,
            admin_client,
            shops_client,
        )

    except Exception as e:
        logger.error(f"Ошибка при обновлении профиля магазина: {e}", exc_info=True)
        await message.answer(
            "❌ Произошла ошибка при сохранении данных магазина. "
            "Пожалуйста, обратитесь к администратору."
        )
        await state.clear()

import asyncio
from contextlib import asynccontextmanager

from backend.src.core.config import LoggingConfig, settings
from rich.console import Console
from rich.panel import Panel

settings.logging.configure_rich()

try:
    from aiogram import Bot, Dispatcher
    from aiogram.fsm.storage.memory import MemoryStorage
    from aiogram.types.error_event import ErrorEvent
    from backend.src.core.config import get_bot_token, settings
    from backend.src.core.logging import get_logger, setup_logging

    from bot.clients import ClientManager
    from bot.clients.base_client import ConnectionPool
    from bot.filters.user_data_filter import UserDataFilter
    from bot.handlers import *
    from bot.middleware import setup_middlewares
    from bot.middleware.token_refresh_middleware import TokenRefreshMiddleware
    from bot.redis_storage import UserDataStorage
    from bot.utils.token_manager import TokenManager

except Exception:
    LoggingConfig.handle_start_exception()

logger = get_logger(__name__)
console = Console(force_terminal=settings.logging.rich_force_terminal)


def create_bot(**kwargs) -> Bot:
    """Создает экземпляр бота."""
    return Bot(token=get_bot_token(), **kwargs)


def create_dispatcher(
    storage, user_data_storage: UserDataStorage, client_manager: ClientManager, **kwargs
) -> Dispatcher:
    dp = Dispatcher(storage=storage, **kwargs)

    setup_middlewares(dp)

    token_refresh_middleware = TokenRefreshMiddleware(
        storage=user_data_storage,
        auth_client=client_manager.auth,
    )
    dp.message.middleware(token_refresh_middleware)
    dp.callback_query.middleware(token_refresh_middleware)

    kwargs["token_refresh_middleware"] = token_refresh_middleware

    user_data_provider = UserDataFilter(user_data_storage)

    for router in [auth_router, protected_router, orders_router, public_router]:
        router.message.filter(user_data_provider)
        router.callback_query.filter(user_data_provider)

    dp.include_router(protected_router)
    dp.include_router(auth_router)
    dp.include_router(orders_router)
    dp.include_router(public_router)

    async def on_unknown_error(event: ErrorEvent):
        logger.critical(f"Критическая ошибка: {event.exception}", exc_info=True)
        if event.update and event.update.message:
            await event.update.message.answer(
                "Произошла непредвиденная ошибка. Мы уже работаем над этим."
            )

    dp.errors.register(on_unknown_error)

    return dp


@asynccontextmanager
async def lifespan():
    """Контекстный менеджер жизненного цикла бота с визуализацией запуска."""

    console.print("[cyan]⚙️  Инициализация компонентов...[/cyan]")

    bot = None
    pool = None
    user_data_storage = None
    token_refresh_middleware = None

    try:
        # Инициализация всех компонентов
        pool = ConnectionPool()
        storage = MemoryStorage()
        user_data_storage = UserDataStorage(settings.redis)
        client_manager = ClientManager(pool=pool)
        bot = create_bot()

        dp_kwargs = {
            "storage": storage,
            "user_data_storage": user_data_storage,
            "client_manager": client_manager,
            "admin_client": client_manager.admin,
            "auth_client": client_manager.auth,
            "disputes_client": client_manager.disputes,
            "notifications_client": client_manager.notifications,
            "orders_client": client_manager.orders,
            "shops_client": client_manager.shops,
            "system_client": client_manager.system,
            "users_client": client_manager.users,
            "couriers_client": client_manager.couriers,
            "user_storage": user_data_storage,
            "token_manager": TokenManager(client_manager.auth, user_data_storage),
        }
        dp = create_dispatcher(**dp_kwargs)

        token_refresh_middleware = dp_kwargs.get("token_refresh_middleware")
        if token_refresh_middleware:
            await token_refresh_middleware.start_cleanup_task()

        try:
            yield bot, dp
        finally:
            # Тихое завершение без визуализации
            if token_refresh_middleware:
                await token_refresh_middleware.stop_cleanup_task()

    finally:
        if user_data_storage:
            await user_data_storage.close()
        if pool:
            await pool.close()
        if bot and bot.session:
            await bot.session.close()


async def run_polling(skip_updates: bool = True):
    """Запуск бота в режиме polling с красивым логированием."""
    async with lifespan() as (bot, dp):
        console.print(
            Panel(
                "[green]Бот готов принимать сообщения!\n[dim]Нажмите Ctrl+C для остановки[/dim]",
                border_style="cyan",
                title="🤖 Bot Active",
            )
        )

        await dp.start_polling(
            bot,
            skip_updates=skip_updates,
            allowed_updates=dp.resolve_used_update_types(),
        )


def main():
    """Главная функция запуска."""
    # Настройка логгирования
    setup_logging()

    # Красивый заголовок
    console.print("\n")

    try:
        asyncio.run(run_polling(skip_updates=settings.telegram.skip_updates))
    except (KeyboardInterrupt, SystemExit):
        console.print("\n")
        console.print(
            Panel(
                "[yellow]👋 Бот остановлен пользователем[/yellow]",
                border_style="yellow",
                title="Shutdown",
            )
        )
    except Exception as e:
        console.print("\n")
        console.print(
            Panel(
                f"[bold red]💥 Критическая ошибка:[/bold red]\n{e}",
                border_style="red",
                title="Error",
            )
        )
        logger.critical(f"💥 Критическая ошибка при запуске бота: {e}", exc_info=True)
        exit(1)


if __name__ == "__main__":
    main()

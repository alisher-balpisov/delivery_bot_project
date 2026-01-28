import asyncio
import re
import sys
import time
from contextlib import asynccontextmanager

from backend.src.core.config import LoggingConfig, settings

settings.logging.configure_rich()

try:
    import psutil
    import uvicorn
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse
    from rich.console import Console
    from rich.live import Live
    from rich.panel import Panel
    from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
    from rich.table import Table
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from slowapi.middleware import SlowAPIMiddleware
    from slowapi.util import get_remote_address

    from backend.src.api.routes import api_router
    from backend.src.core.config import ensure_upload_dir_exists, settings
    from backend.src.core.database import close_db, init_db
    from backend.src.core.logging import get_logger, setup_logging

except Exception:
    LoggingConfig.handle_start_exception()

logger = get_logger(__name__)
console = Console(force_terminal=settings.logging.rich_force_terminal)

# Паттерны для потенциально опасных данных
DANGEROUS_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r";\s*--",
        r";\s*/\*",
        r"<\s*script",
        r"javascript\s*:",
        r"on\w+\s*=",
    ]
]


async def startup_with_progress():
    """Запуск приложения с визуализацией прогресса"""

    tasks = [
        ("Initializing database", init_db),
        ("Creating directories", lambda: ensure_upload_dir_exists()),
        ("Loading configuration", lambda: asyncio.sleep(0.09)),
        ("Setting up middleware", lambda: asyncio.sleep(0.07)),
        ("Registering routes", lambda: asyncio.sleep(0.05)),
    ]

    # Красивый заголовок
    header = Panel.fit(
        f"[bold cyan]{settings.app_name}[/bold cyan] [yellow]v{settings.app_version}[/yellow]\n"
        f"[dim]Starting application...[/dim]",
        border_style="cyan",
    )

    with Live(header, console=console, refresh_per_second=10, transient=True):
        await asyncio.sleep(0.5)  # Показываем заголовок немного

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
        transient=True,  # Прогресс-бар исчезнет после завершения
    ) as progress:
        main_task = progress.add_task("[cyan]Starting up...", total=len(tasks))

        for description, func in tasks:
            task = progress.add_task(f"[yellow]{description}", total=1)

            try:
                if asyncio.iscoroutinefunction(func):
                    await func()
                else:
                    result = func()
                    if asyncio.iscoroutine(result):
                        await result

                progress.update(task, completed=1, description=f"[green]✓ {description}")
                progress.advance(main_task)
                await asyncio.sleep(0.05)

            except Exception as e:
                progress.update(task, description=f"[red]✗ {description}")
                logger.error(f"Failed: {description} - {e}", exc_info=True)
                raise

    # Итоговая информация
    info_table = Table(show_header=False, box=None, padding=(0, 2))
    info_table.add_row("[green]✓[/green]", "Application", f"[bold]{settings.app_name}[/bold]")
    info_table.add_row("[green]✓[/green]", "Version", f"[cyan]{settings.app_version}[/cyan]")
    info_table.add_row(
        "[green]✓[/green]", "Environment", f"[yellow]{settings.environment}[/yellow]"
    )
    info_table.add_row(
        "[green]✓[/green]", "Server", f"[link]http://{settings.api_host}:{settings.api_port}[/link]"
    )
    info_table.add_row(
        "[green]✓[/green]",
        "Docs",
        f"[link]http://{settings.api_host}:{settings.api_port}{settings.docs_url or '/docs'}[/link]",
    )

    console.print(Panel(info_table, title="[bold green]🚀 Ready!", border_style="green"))
    console.print()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""

    try:
        await startup_with_progress()
        logger.info("Application started successfully")
    except Exception as e:
        logger.critical(f"Failed to start application: {e}", exc_info=True)
        raise

    yield

    try:
        console.print("\n[yellow]Shutting down...[/yellow]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("[yellow]Closing database connections...", total=None)
            await close_db()
            progress.update(task, description="[green]✓ Database closed")

        console.print("[green]✓ Shutdown complete[/green]\n")

    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


def create_app() -> FastAPI:
    """Создание и настройка FastAPI приложения"""
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url=settings.docs_url,
        redoc_url=settings.redoc_url,
        lifespan=lifespan,
    )

    limiter = Limiter(key_func=get_remote_address)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    # Middleware санитизации
    @app.middleware("http")
    async def sanitize_input(request: Request, call_next):
        if request.method in ["POST", "PUT", "PATCH"]:
            content_type = request.headers.get("content-type", "")
            if "application/json" in content_type or "text/" in content_type:
                try:
                    body = await request.body()
                    if len(body) > 1024 * 64:
                        return await call_next(request)

                    body_str = body.decode("utf-8", errors="ignore")
                    for pattern in DANGEROUS_PATTERNS:
                        if pattern.search(body_str):
                            logger.warning(f"Suspicious input detected: {request.url}")
                            raise HTTPException(
                                status_code=400, detail="Blocked by security policy."
                            )
                except HTTPException:
                    raise
                except Exception as e:
                    logger.error(f"Error in sanitize middleware: {e}")

        return await call_next(request)

    app.add_middleware(CORSMiddleware, **settings.middleware.cors_kwargs())

    # Middleware логирования
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start_time = time.time()
        try:
            response = await call_next(request)
            process_time = time.time() - start_time
            logger.info(
                f"{request.method} {request.url} - {response.status_code} - {process_time:.4f}s"
            )
            return response
        except Exception as e:
            process_time = time.time() - start_time
            logger.error(
                f"{request.method} {request.url} - ERROR: {e} - {process_time:.4f}s",
                exc_info=True,
            )
            raise

    app.include_router(api_router, prefix=settings.api_prefix)

    @app.get("/")
    async def root():
        return JSONResponse(
            {
                "message": f"Welcome to {settings.app_name}!",
                "version": settings.app_version,
                "docs": "/docs" if settings.docs_url else "Disabled",
            }
        )

    @app.get(f"{settings.api_prefix}/health")
    async def health_check():
        process = psutil.Process()
        return {
            "status": "healthy",
            "metrics": {
                "memory_mb": process.memory_info().rss / 1024 / 1024,
                "uptime": time.time() - process.create_time(),
            },
        }

    return app


app = create_app()


async def run_app():
    """Запуск приложения"""
    try:
        setup_logging()
        app = create_app()

        config = uvicorn.Config(
            app,
            host=settings.api_host,
            port=settings.api_port,
            log_level=settings.logging.level.lower(),
            access_log=settings.debug,
            reload=settings.debug and settings.is_development,
            log_config=None,
        )

        server = uvicorn.Server(config)
        await server.serve()

    except KeyboardInterrupt:
        console.print("\n[yellow]⏹️  Interrupted by user[/yellow]")
    except Exception as e:
        console.print(f"\n[red]💥 Critical error: {e}[/red]")
        logger.critical(f"Critical error: {e}", exc_info=True)
        sys.exit(1)


def main():
    try:
        asyncio.run(run_app())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        console.print(f"[red]Critical launch error: {e}[/red]")
        sys.exit(1)


async def run_api_only():
    setup_logging()

    console.print("[cyan]Starting API-only mode...[/cyan]")
    await init_db()

    app = FastAPI(title="API Only")
    app.include_router(api_router, prefix=settings.api_prefix)

    config = uvicorn.Config(app, host=settings.api_host, port=settings.api_port, log_config=None)
    server = uvicorn.Server(config)

    try:
        console.print(
            f"[green]API running on http://{settings.api_host}:{settings.api_port}[/green]"
        )
        await server.serve()
    finally:
        await close_db()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "api":
        asyncio.run(run_api_only())
    else:
        main()

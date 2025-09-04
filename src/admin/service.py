import hashlib
import json
import secrets
import string
from datetime import datetime

import redis.asyncio as redis
from src.core.config import settings
from src.core.logging import get_logger
from src.schemas.admin import OneTimeCodeRead

logger = get_logger(__name__)

# Redis connection
redis_client: redis.Redis | None = None


async def init_redis_client() -> redis.Redis:
    """Инициализировать и возвратить Redis клиент."""
    try:
        client = redis.from_url(settings.redis.url, decode_responses=True)
        await client.ping()
        logger.info("✅ Redis connection established for OTC service")
        return client
    except Exception as e:
        logger.error(f"❌ Redis connection failed: {e}")
        raise ConnectionError(f"Cannot connect to Redis: {e}")


async def generate_one_time_code(telegram_id: int, user_role: str) -> OneTimeCodeRead:
    """
    Генерирует одноразовый код для регистрации и сохраняет его в Redis.

    Args:
        telegram_id: ID пользователя, для которого генерируется код.
        user_role: Роль, назначаемая пользователю после активации кода.

    Returns:
        Схема с данными сгенерированного кода.
    """
    try:
        client = await init_redis_client()
        # Более безопасная генерация с проверкой на столкновения
        for _ in range(10):
            code = "".join(secrets.choice(string.digits) for _ in range(6))

            # Проверить уникальность
            if not await client.exists(f"otc:{code}"):
                break
        else:
            raise RuntimeError("Cannot generate unique code after 10 attempts")

        # Добавить хеширование для дополнительной безопасности
        code_hash = hashlib.sha256(f"{code}{telegram_id}".encode()).hexdigest()[:8]

        data = {
            "telegram_id": telegram_id,
            "user_role": user_role,
            "is_used": False,
            "created_at": datetime.now().isoformat(),
            "code_hash": code_hash,  # Для дополнительной проверки
        }

        # Сократить TTL для безопасности
        await client.setex(f"otc:{code}", 1800, json.dumps(data))  # 30 минут вместо часа

        logger.info(f"🔑 Generated OTC for user {telegram_id} with role {user_role}")
        return OneTimeCodeRead(code=code, user_role=user_role, is_used=False)

    except Exception as e:
        logger.error(f"❌ Error generating OTC: {e}")
        raise


async def verify_one_time_code(code: str) -> OneTimeCodeRead | None:
    """
    Проверяет одноразовый код.

    Args:
        code: Одноразовый код для проверки.

    Returns:
        Схема с данными кода, если он валиден, иначе None.
    """
    try:
        client = await init_redis_client()

        # Get data from Redis
        data_str = await client.get(f"otc:{code}")
        if not data_str:
            logger.warning(f"❌ OTC '{code}' not found or expired")
            return None

        data = json.loads(data_str)

        # Check if already used
        if data.get("is_used", False):
            logger.warning(f"⚠️ OTC '{code}' already used")
            return None

        # Mark as used
        data["is_used"] = True
        await client.setex(f"otc:{code}", 3600, json.dumps(data))

        logger.info(f"✅ OTC '{code}' verified for user {data['telegram_id']}")
        return OneTimeCodeRead(code=code, user_role=data["user_role"], is_used=True)

    except json.JSONDecodeError as e:
        logger.error(f"❌ Malformed OTC data for '{code}': {e}")
        return None
    except Exception as e:
        logger.error(f"❌ Error verifying OTC '{code}': {e}")
        return None

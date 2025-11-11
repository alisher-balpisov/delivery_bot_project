import json
from typing import Any

import redis.asyncio as redis
from backend.src.core.config import RedisConfig
from redis.asyncio import Redis


class UserDataStorage:
    def __init__(self, config: RedisConfig):
        self.config = config
        self.redis_client: Redis | None = None

    async def get_redis_client(self) -> Redis:
        if self.redis_client is None:
            self.redis_client = redis.Redis(
                host=self.config.host,
                port=self.config.port,
                db=self.config.db,
                decode_responses=True,
            )
        return self.redis_client

    async def get_data(self, user_id: int) -> dict[str, Any]:
        client = await self.get_redis_client()
        data = await client.get(str(user_id))
        if data:
            return json.loads(data)
        return {}

    async def set_data(self, user_id: int, data: dict[str, Any]) -> None:
        client = await self.get_redis_client()
        await client.set(str(user_id), json.dumps(data), ex=self.config.data_ttl)

    async def update_data(self, user_id: int, data: dict[str, Any]) -> None:
        client = await self.get_redis_client()
        current_data = await self.get_data(user_id)
        current_data.update(data)
        await client.set(str(user_id), json.dumps(current_data), ex=self.config.data_ttl)

    async def delete_data(self, user_id: int) -> None:
        client = await self.get_redis_client()
        await client.delete(str(user_id))

    async def get_field(self, user_id: int, field: str) -> Any:
        data = await self.get_data(user_id)
        return data.get(field)

    async def close(self) -> None:
        if self.redis_client:
            await self.redis_client.close()


__all__ = ["UserDataStorage"]

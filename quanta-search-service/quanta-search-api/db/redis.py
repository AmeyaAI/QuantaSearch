from typing import Dict, List, Any, Optional
from redis.asyncio import Redis
from redis.exceptions import RedisError
import json

from utils.load_envs import env


class RedisRepository:
    """Base repository class for Redis operations."""

    def __init__(self, client: Redis):
        """Initialize repository with Redis client instance.

        Args:
            client: Async Redis client instance.
        """
        self.client = client

    async def find_one(self, key: str) -> Optional[Dict]:
        """Find a single value by key.

        Args:
            key: Redis key.

        Returns:
            Dictionary value or None if key doesn't exist.

        Raises:
            Exception: If Redis operation fails.
        """
        try:
            value = await self.client.get(key)
            return json.loads(value) if value else None
        except RedisError as e:
            raise Exception(f"Redis error in find_one: {str(e)}")

    async def find_all(self, pattern: str = "*") -> List[Dict]:
        """Find all keys matching a pattern and return their values.

        Args:
            pattern: Redis key pattern (default is '*' to match all keys).

        Returns:
            List of dictionaries representing the values.

        Raises:
            Exception: If Redis operation fails.
        """
        try:
            keys = await self.client.keys(pattern)
            if keys:
                values = await self.client.mget(keys)
                return [json.loads(value) for value in values if value]
            return []
        except RedisError as e:
            raise Exception(f"Redis error in find_all: {str(e)}")

    async def insert_one(self, key: str, value: Dict, ex: Optional[int] = None) -> bool:
        """Insert a single key-value pair.

        Args:
            key: Redis key.
            value: Dictionary value to store.
            ex: Optional expiration time in seconds.

        Returns:
            True if the operation was successful.

        Raises:
            Exception: If Redis operation fails.
        """
        try:
            result = await self.client.set(key, json.dumps(value), ex=ex)
            return result
        except RedisError as e:
            raise Exception(f"Redis error in insert_one: {str(e)}")

    async def insert_many(self, data: Dict[str, Dict]) -> bool:
        """Insert multiple key-value pairs.

        Args:
            data: Dictionary of key-value pairs to insert.

        Returns:
            True if the operation was successful.

        Raises:
            Exception: If Redis operation fails.
        """
        try:
            pipeline = self.client.pipeline()
            for key, value in data.items():
                pipeline.set(key, json.dumps(value))
            await pipeline.execute()
            return True
        except RedisError as e:
            raise Exception(f"Redis error in insert_many: {str(e)}")

    async def update_one(self, key: str, value: Dict) -> bool:
        """Update a single key-value pair.

        Args:
            key: Redis key.
            value: Dictionary value to update.

        Returns:
            True if the operation was successful.

        Raises:
            Exception: If Redis operation fails.
        """
        try:
            existing_value = await self.find_one(key)
            if existing_value:
                existing_value.update(value)
                return await self.insert_one(key, existing_value)
            return False
        except RedisError as e:
            raise Exception(f"Redis error in update_one: {str(e)}")

    async def delete_one(self, key: str) -> int:
        """Delete a single key.

        Args:
            key: Redis key.

        Returns:
            Number of keys deleted (0 or 1).

        Raises:
            Exception: If Redis operation fails.
        """
        try:
            return await self.client.delete(key)
        except RedisError as e:
            raise Exception(f"Redis error in delete_one: {str(e)}")

    async def delete_many(self, pattern: str = "*") -> int:
        """Delete multiple keys matching a pattern.

        Args:
            pattern: Redis key pattern (default is '*' to match all keys).

        Returns:
            Number of keys deleted.

        Raises:
            Exception: If Redis operation fails.
        """
        try:
            keys = await self.client.keys(pattern)
            if keys:
                return await self.client.delete(*keys)
            return 0
        except RedisError as e:
            raise Exception(f"Redis error in delete_many: {str(e)}")

    async def count(self, pattern: str = "*") -> int:
        """Count keys matching a pattern.

        Args:
            pattern: Redis key pattern (default is '*' to match all keys).

        Returns:
            Number of keys matching the pattern.

        Raises:
            Exception: If Redis operation fails.
        """
        try:
            keys = await self.client.keys(pattern)
            return len(keys)
        except RedisError as e:
            raise Exception(f"Redis error in count: {str(e)}")


class RedisDB(RedisRepository):
    
    def __init__(self):
        self.client = Redis(host=env.REDIS_HOST, port=env.REDIS_PORT, decode_responses=True, db=1)


cache = RedisDB()

        
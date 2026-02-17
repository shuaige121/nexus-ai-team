"""Redis Streams queue manager — producer and consumer for work orders."""

from __future__ import annotations

import json
import logging
from typing import Any

import redis.asyncio as redis

logger = logging.getLogger(__name__)


class QueueManager:
    """Redis Streams producer/consumer for work order queue."""

    def __init__(self, redis_url: str, stream_name: str = "nexus:work_orders") -> None:
        self.redis_url = redis_url
        self.stream_name = stream_name
        self._client: redis.Redis | None = None

    async def connect(self) -> None:
        """Establish Redis connection."""
        self._client = await redis.from_url(
            self.redis_url,
            decode_responses=True,
            encoding="utf-8",
        )
        await self._client.ping()
        logger.info("QueueManager connected to Redis")

    async def close(self) -> None:
        """Close Redis connection."""
        if self._client:
            await self._client.aclose()
            self._client = None
            logger.info("QueueManager disconnected")

    async def enqueue(self, work_order_id: str, payload: dict[str, Any]) -> str:
        """
        Publish a work order to the Redis Stream.

        Returns the stream entry ID (e.g., '1234567890-0').
        """
        if not self._client:
            raise RuntimeError("Redis not connected. Call connect() first.")

        data = {
            "work_order_id": work_order_id,
            "payload": json.dumps(payload, ensure_ascii=False),
        }
        entry_id = await self._client.xadd(self.stream_name, data)
        logger.info("Enqueued work order %s -> stream entry %s", work_order_id, entry_id)
        return entry_id

    async def consume(
        self,
        consumer_group: str = "nexus-dispatcher",
        consumer_name: str = "worker-1",
        count: int = 1,
        block_ms: int = 5000,
    ) -> list[dict[str, Any]]:
        """
        Consume messages from the Redis Stream using consumer group.

        Returns a list of messages in the format:
        [
            {
                "stream": "nexus:work_orders",
                "entry_id": "1234567890-0",
                "work_order_id": "WO-...",
                "payload": {...}
            }
        ]
        """
        if not self._client:
            raise RuntimeError("Redis not connected.")

        # Ensure consumer group exists (idempotent)
        try:
            await self._client.xgroup_create(
                name=self.stream_name,
                groupname=consumer_group,
                id="0",
                mkstream=True,
            )
            logger.debug("Created consumer group: %s", consumer_group)
        except redis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise

        # Read from the stream
        raw_messages = await self._client.xreadgroup(
            groupname=consumer_group,
            consumername=consumer_name,
            streams={self.stream_name: ">"},
            count=count,
            block=block_ms,
        )

        messages: list[dict[str, Any]] = []
        for stream, entries in raw_messages:
            for entry_id, data in entries:
                work_order_id = data.get("work_order_id", "")
                payload_str = data.get("payload", "{}")
                try:
                    payload = json.loads(payload_str)
                except json.JSONDecodeError:
                    payload = {}

                messages.append(
                    {
                        "stream": stream,
                        "entry_id": entry_id,
                        "work_order_id": work_order_id,
                        "payload": payload,
                    }
                )

        if messages:
            logger.debug("Consumed %d message(s) from %s", len(messages), self.stream_name)

        return messages

    async def ack(
        self,
        entry_id: str,
        consumer_group: str = "nexus-dispatcher",
    ) -> None:
        """Acknowledge a message has been processed."""
        if not self._client:
            raise RuntimeError("Redis not connected.")

        await self._client.xack(self.stream_name, consumer_group, entry_id)
        logger.debug("ACKed stream entry: %s", entry_id)

    async def publish_event(self, channel: str, event: dict[str, Any]) -> None:
        """Publish a real-time event to a Redis pub/sub channel."""
        if not self._client:
            raise RuntimeError("Redis not connected.")

        payload = json.dumps(event, ensure_ascii=False)
        await self._client.publish(channel, payload)
        logger.debug("Published event to channel %s", channel)

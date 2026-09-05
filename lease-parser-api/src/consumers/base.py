"""Kafka consumer/producer scaffolding (T006, contracts/events.md).

Wraps confluent-kafka with JSON (de)serialization and a durable
retry/dead-letter pattern, satisfying FR-010: an outage delays processing,
it never drops work. This is the platform's existing event bus
(commercial-brokerage-platform-design.md §6) — this service plugs into it
rather than introducing a second messaging technology (research.md).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from confluent_kafka import Consumer, KafkaError, KafkaException, Message, Producer

from src.config import get_settings

logger = logging.getLogger(__name__)

MessageHandler = Callable[[dict[str, Any]], Awaitable[None]]


class JsonProducer:
    """Thin JSON-serializing wrapper around confluent_kafka.Producer."""

    def __init__(self, bootstrap_servers: str | None = None) -> None:
        settings = get_settings()
        self._producer = Producer(
            {"bootstrap.servers": bootstrap_servers or settings.kafka_bootstrap_servers}
        )

    def publish(self, topic: str, payload: dict[str, Any], key: str | None = None) -> None:
        self._producer.produce(
            topic=topic,
            key=key,
            value=json.dumps(payload).encode("utf-8"),
            callback=self._delivery_callback,
        )
        self._producer.poll(0)

    def flush(self, timeout: float = 10.0) -> None:
        self._producer.flush(timeout)

    @staticmethod
    def _delivery_callback(err, msg: Message) -> None:
        if err is not None:
            logger.error("Kafka delivery failed for topic %s: %s", msg.topic(), err)


class RetryingConsumer:
    """Consumer group wrapper with bounded retries and dead-letter publishing.

    Satisfies FR-010: on a failure the message is retried up to
    `max_retries` times; once exhausted it is published to the dead-letter
    topic instead of being silently dropped.
    """

    def __init__(
        self,
        topics: list[str],
        group_id: str,
        dead_letter_topic: str,
        max_retries: int = 3,
        bootstrap_servers: str | None = None,
    ) -> None:
        settings = get_settings()
        self._consumer = Consumer(
            {
                "bootstrap.servers": bootstrap_servers or settings.kafka_bootstrap_servers,
                "group.id": group_id,
                "enable.auto.commit": False,
                "auto.offset.reset": "earliest",
            }
        )
        self._consumer.subscribe(topics)
        self._dead_letter_topic = dead_letter_topic
        self._max_retries = max_retries
        self._producer = JsonProducer(bootstrap_servers)

    async def run_once(self, handler: MessageHandler, timeout: float = 1.0) -> bool:
        """Poll a single message and process it. Returns True if a message was handled."""
        msg = self._consumer.poll(timeout)
        if msg is None:
            return False
        if msg.error():
            if msg.error().code() == KafkaError._PARTITION_EOF:
                return False
            raise KafkaException(msg.error())

        payload = json.loads(msg.value().decode("utf-8"))
        attempt = 0
        while True:
            try:
                await handler(payload)
                self._consumer.commit(msg)
                return True
            except Exception:
                attempt += 1
                logger.exception(
                    "Handler failed for message on %s (attempt %d/%d)",
                    msg.topic(),
                    attempt,
                    self._max_retries,
                )
                if attempt >= self._max_retries:
                    self._producer.publish(
                        self._dead_letter_topic,
                        {
                            "documentId": payload.get("documentId"),
                            "originalEvent": payload,
                            "failureReason": "handler_exhausted_retries",
                            "attemptCount": attempt,
                        },
                    )
                    self._consumer.commit(msg)
                    return True

    def close(self) -> None:
        self._consumer.close()
        self._producer.flush()

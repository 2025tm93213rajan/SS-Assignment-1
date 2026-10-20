import json
import logging
from typing import Dict, Any
import aio_pika
from src.config import settings

logger = logging.getLogger(settings.SERVICE_NAME)

class EventPublisher:
    def __init__(self):
        self._connection = None
        self._channel = None
        self._exchange = None

    async def connect(self):
        try:
            self._connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
            self._channel = await self._connection.channel()
            self._exchange = await self._channel.declare_exchange(
                settings.RABBITMQ_EXCHANGE,
                aio_pika.ExchangeType.TOPIC,
                durable=True
            )
            logger.info(f"Connected to RabbitMQ exchange '{settings.RABBITMQ_EXCHANGE}'")
        except Exception as e:
            logger.warning(f"RabbitMQ connection failed (will retry on publish): {str(e)}")

    async def publish(self, routing_key: str, payload: Dict[str, Any], correlation_id: str = "unknown") -> bool:
        try:
            if not self._channel or self._channel.is_closed:
                await self.connect()

            message = aio_pika.Message(
                body=json.dumps(payload).encode("utf-8"),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                correlation_id=correlation_id,
                content_type="application/json"
            )
            await self._exchange.publish(message, routing_key=routing_key)
            logger.info(f"Published event '{routing_key}' to RabbitMQ correlation_id={correlation_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to publish event '{routing_key}' to RabbitMQ: {str(e)}")
            return False

    async def close(self):
        if self._connection and not self._connection.is_closed:
            await self._connection.close()

event_publisher = EventPublisher()

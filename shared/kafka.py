"""Thin Kafka producer / consumer helpers using confluent-kafka and asyncio.to_thread."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from confluent_kafka import Producer, Consumer, KafkaError, TopicPartition
from confluent_kafka.admin import AdminClient, NewTopic

from shared.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class AsyncKafkaProducer:
    def __init__(self, bootstrap_servers: str):
        self.producer = Producer({
            'bootstrap.servers': bootstrap_servers,
            'client.id': 'swiftride-producer',
        })

    def _delivery_report(self, err, msg):
        """Called once for each message produced to indicate delivery result."""
        if err is not None:
            logger.error(f'Message delivery failed: {err}')
        else:
            logger.debug(f'Message delivered to {msg.topic()} [{msg.partition()}]')

    def _produce_sync(self, topic: str, value: bytes, key: bytes | None, headers: dict | None = None):
        self.producer.produce(
            topic,
            value=value,
            key=key,
            headers=headers,
            on_delivery=self._delivery_report
        )
        self.producer.poll(0)

    async def produce(self, topic: str, value: dict[str, Any], key: str | None = None, headers: dict | None = None) -> None:
        val_bytes = json.dumps(value).encode('utf-8')
        key_bytes = key.encode('utf-8') if key else None
        
        norm_headers = []
        if headers:
            for k, v in headers.items():
                if isinstance(v, str):
                    norm_headers.append((k, v.encode('utf-8')))
                elif isinstance(v, bytes):
                    norm_headers.append((k, v))
                elif isinstance(v, int):
                    norm_headers.append((k, str(v).encode('utf-8')))

        await asyncio.to_thread(self._produce_sync, topic, val_bytes, key_bytes, norm_headers)

    async def flush(self):
        await asyncio.to_thread(self.producer.flush)
        
    async def stop(self):
        await self.flush()


class AsyncKafkaConsumer:
    def __init__(self, bootstrap_servers: str, group_id: str, enable_auto_commit: bool = True, auto_offset_reset: str = 'latest'):
        self.group_id = group_id
        self.consumer = Consumer({
            'bootstrap.servers': bootstrap_servers,
            'group.id': group_id,
            'auto.offset.reset': auto_offset_reset,
            'enable.auto.commit': enable_auto_commit
        })
        self._shutdown = False

    def subscribe(self, topics: List[str]):
        self.consumer.subscribe(topics)

    def _poll_sync(self, timeout: float):
        msg = self.consumer.poll(timeout)
        if msg is None:
            return None
        if msg.error():
            if msg.error().code() == KafkaError._PARTITION_EOF:
                return None
            else:
                raise Exception(f"Kafka error: {msg.error()}")
        return msg

    async def poll(self, timeout: float = 1.0) -> dict | None:
        if self._shutdown:
            return None
            
        msg = await asyncio.to_thread(self._poll_sync, timeout)
        if msg is None:
            return None
            
        val = msg.value()
        val_dict = json.loads(val.decode('utf-8')) if val else None
        
        headers_dict = {}
        if msg.headers():
            for key, val in msg.headers():
                if val:
                    headers_dict[key] = val.decode('utf-8')
                else:
                    headers_dict[key] = None
                    
        return {
            "value": val_dict,
            "key": msg.key().decode('utf-8') if msg.key() else None,
            "headers": headers_dict,
            "topic": msg.topic()
        }

    async def commit(self):
        """Manually commit offsets."""
        await asyncio.to_thread(self.consumer.commit, asynchronous=False)

    def _get_lag_sync(self, topic: str) -> int:
        partitions = self.consumer.assignment()
        topic_partitions = [p for p in partitions if p.topic == topic]
        
        if not topic_partitions:
            return 0
            
        committed = self.consumer.committed(topic_partitions, timeout=5.0)
        
        total_lag = 0
        for p in committed:
            if p.offset == KafkaError._UNASSIGNED or p.offset < 0:
                continue
            low, high = self.consumer.get_watermark_offsets(p, timeout=5.0, cached=False)
            if high > p.offset:
                total_lag += (high - p.offset)
                
        return total_lag
        
    async def get_lag(self, topic: str) -> int:
        try:
            return await asyncio.to_thread(self._get_lag_sync, topic)
        except Exception as e:
            logger.error(f"Error getting lag: {e}")
            return 0

    async def get_health(self, topic: str) -> dict:
        lag = await self.get_lag(topic)
        status = "healthy"
        if lag > 500:
            status = "critical"
        elif lag > 100:
            status = "degraded"
            
        return {
            "consumer_group": self.group_id,
            "topic": topic,
            "lag": lag,
            "status": status
        }

    async def stop(self):
        self._shutdown = True
        await asyncio.to_thread(self.consumer.close)


async def create_producer() -> AsyncKafkaProducer:
    return AsyncKafkaProducer(settings.kafka_bootstrap_servers)


async def create_consumer(*topics: str, group_id: str | None = None, enable_auto_commit: bool = True, auto_offset_reset: str = 'latest') -> AsyncKafkaConsumer:
    consumer = AsyncKafkaConsumer(
        settings.kafka_bootstrap_servers, 
        group_id or settings.kafka_group_id,
        enable_auto_commit=enable_auto_commit,
        auto_offset_reset=auto_offset_reset
    )
    consumer.subscribe(list(topics))
    return consumer


async def publish(producer: AsyncKafkaProducer, topic: str, value: dict[str, Any], key: str | None = None, headers: dict | None = None) -> None:
    """Publish a single message to a Kafka topic."""
    await producer.produce(topic, value, key, headers)
    logger.info("Published to %s key=%s", topic, key)

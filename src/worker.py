import asyncio
import logging
import os
from asyncio import Queue
from typing import List

import httpx
import redis
import json
import traceback

from sqlalchemy import text

from src.buffer import PaymentBuffer
from src.db import get_db_session, Payment
from src.schemas import ProcessedPayment


class Cache:
    def __init__(self):
        self.client = redis.Redis(host="cache", port=6379, decode_responses=True)

    def get(self, key: str):
        return self.client.get(key)

    def set(self, key: str, value: str):
        return self.client.set(key, value)

class PaymentRepo:
    def save_batch(self, payments: List[ProcessedPayment]):
        """Ultra-fast batch insert using raw SQL"""
        if not payments:
            return

        # Build VALUES clause for all payments
        values = []
        params = {}

        for i, payment in enumerate(payments):
            values.append(f"(:correlation_id_{i}, :processor_{i}, :amount_{i}, :requested_at_{i})")
            params[f'correlation_id_{i}'] = str(payment.correlationId)
            params[f'processor_{i}'] = payment.processor
            params[f'amount_{i}'] = payment.amount
            params[f'requested_at_{i}'] = payment.requestedAt

        sql = f"""
            INSERT INTO payments ("correlationId", processor, amount, "requestedAt")
            VALUES {', '.join(values)}
            ON CONFLICT ("correlationId") DO NOTHING
        """

        with get_db_session() as session:
            session.execute(text(sql), params)

    def save(self, payment: ProcessedPayment):
        new_payment = Payment(**payment.to_dict())
        with get_db_session() as session:
            session.add(new_payment)

    def get_all(self):
        with get_db_session() as session:
            payments = session.query(Payment).all()
            return [ProcessedPayment.model_validate(payment) for payment in payments]

    def purge(self):
        with get_db_session() as session:
            payments = session.query(Payment).all()
            for payment in payments:
                session.delete(payment)
            session.commit()

class PaymentApi:
    def __init__(self, cache: Cache):
        self.__default_payment_processor = os.getenv("DEFAULT_PAYMENT_PROCESSOR")
        self.__fallback_payment_processor = os.getenv("FALLBACK_PAYMENT_PROCESSOR")
        self.cache = cache
        self.client = httpx.AsyncClient(timeout=10.0)
    
    async def send_payment_default(self, payment: dict) -> int:
        response = await self.client.post(f"{self.__default_payment_processor}/payments", json=payment)

        return response.status_code

    async def send_payment_fallback(self, payment: dict) -> int:
        response = await self.client.post(f"{self.__fallback_payment_processor}/payments", json=payment)

        return response.status_code


class PaymentProcessor:
    def __init__(self, health_manager, repo: PaymentRepo):
        self.health_manager = health_manager
        self.payment_buffer = PaymentBuffer(repo, batch_size=50, flush_interval=1.5)
        self.repo = repo
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(10.0),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10)
        )

    async def process_single_payment(self, payment: dict) -> bool:
        """Process payment and add to buffer instead of immediate save"""
        correlation_id = payment['correlationId']

        processor_type = self.health_manager.choose_best_processor()

        if await self._send_payment(payment, processor_type):
            processed_payment = ProcessedPayment(
                processor=processor_type,
                **payment
            )
            await self.payment_buffer.add_payment(processed_payment)
            return True

        alternative = "fallback" if processor_type == "default" else "default"
        if await self._send_payment(payment, alternative):
            processed_payment = ProcessedPayment(
                processor=alternative,
                **payment
            )
            await self.payment_buffer.add_payment(processed_payment)
            return True

        return False

    async def _send_payment(self, payment: dict, processor_type: str) -> bool:
        """Send payment to specific processor"""
        if processor_type == "default":
            url = "http://payment-processor-default:8080/payments"
        else:
            url = "http://payment-processor-fallback:8080/payments"

        try:
            response = await self.client.post(url, json=payment)
            return response.status_code == 200
        except Exception as e:
            logging.error(f"Error sending to {processor_type}: {e}")
            return False

    async def shutdown(self):
        """Ensure all buffered payments are saved before shutdown"""
        await self.payment_buffer.force_flush()
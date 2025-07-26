import asyncio
import logging
import os
from typing import List

import httpx
import redis

from psycopg2 import IntegrityError, OperationalError
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
    def __init__(self):
        self.retry_delay = 0.1
        self.max_retries = 3

    def save_batch(self, payments: List[ProcessedPayment]):
        """Ultra-reliable batch insert with comprehensive error handling"""
        if not payments:
            return

        if self._try_batch_insert(payments):
            return

        logging.warning(
            f"Batch insert failed, trying individual inserts for {len(payments)} payments"
        )
        self._fallback_individual_inserts(payments)

    def _try_batch_insert(self, payments: List[ProcessedPayment]) -> bool:
        """Attempt batch insert with retries"""
        for attempt in range(self.max_retries):
            try:
                values = []
                params = {}

                for i, payment in enumerate(payments):
                    values.append(
                        f"(:correlation_id_{i}, :processor_{i}, :amount_{i}, :requested_at_{i})"
                    )
                    params[f"correlation_id_{i}"] = str(payment.correlationId)
                    params[f"processor_{i}"] = payment.processor
                    params[f"amount_{i}"] = payment.amount
                    params[f"requested_at_{i}"] = payment.requestedAt

                sql = f"""
                    INSERT INTO payments ("correlationId", processor, amount, "requestedAt")
                    VALUES {", ".join(values)}
                    ON CONFLICT ("correlationId") DO NOTHING
                """

                with get_db_session() as session:
                    result = session.execute(text(sql), params)
                    if result.rowcount >= 0:
                        return True

            except (IntegrityError, OperationalError) as e:
                logging.warning(f"Batch insert attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    asyncio.get_event_loop().run_until_complete(
                        asyncio.sleep(self.retry_delay * (attempt + 1))
                    )
                continue
            except Exception as e:
                logging.error(f"Unexpected error in batch insert: {e}")
                self._fallback_individual_inserts(payments)
                return True
        logging.info(f"Enviou mas não salvou: {len(payments)}")
        return False

    def _fallback_individual_inserts(self, payments: List[ProcessedPayment]):
        """Fallback to individual inserts if batch fails"""
        failed_payments = []

        for payment in payments:
            try:
                with get_db_session() as session:
                    existing = (
                        session.query(Payment)
                        .filter(Payment.correlationId == str(payment.correlationId))
                        .first()
                    )

                    if not existing:
                        new_payment = Payment(
                            correlationId=str(payment.correlationId),
                            processor=payment.processor,
                            amount=payment.amount,
                            requestedAt=payment.requestedAt,
                        )
                        session.add(new_payment)
                        session.commit()

            except Exception as e:
                logging.error(
                    f"Failed to save individual payment {payment.correlationId}: {e}"
                )
                failed_payments.append(payment)

        if failed_payments:
            logging.critical(
                f"Permanently failed to save {len(failed_payments)} payments"
            )

    def get_all(self):
        """Get all payments with error handling"""
        try:
            with get_db_session() as session:
                payments = session.query(Payment).all()
                return [
                    ProcessedPayment.model_validate(payment) for payment in payments
                ]
        except Exception as e:
            logging.error(f"Failed to retrieve payments: {e}")
            return []

    def purge(self):
        """Purge all payments with verification"""
        try:
            with get_db_session() as session:
                deleted_count = session.query(Payment).delete()
                session.commit()
                logging.info(f"Purged {deleted_count} payments")
                return True
        except Exception as e:
            logging.error(f"Failed to purge payments: {e}")
            return False


class PaymentApi:
    def __init__(self, cache: Cache):
        self.__default_payment_processor = os.getenv("DEFAULT_PAYMENT_PROCESSOR")
        self.__fallback_payment_processor = os.getenv("FALLBACK_PAYMENT_PROCESSOR")
        self.cache = cache
        self.client = httpx.AsyncClient(timeout=10.0)

    async def send_payment_default(self, payment: dict) -> int:
        response = await self.client.post(
            f"{self.__default_payment_processor}/payments", json=payment
        )

        return response.status_code

    async def send_payment_fallback(self, payment: dict) -> int:
        response = await self.client.post(
            f"{self.__fallback_payment_processor}/payments", json=payment
        )

        return response.status_code


class PaymentProcessor:
    def __init__(self, health_manager, repo: PaymentRepo):
        self.health_manager = health_manager
        self.payment_buffer = PaymentBuffer(repo, batch_size=50, flush_interval=1.5)
        self.repo = repo
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(10.0),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )

    async def process_single_payment(self, payment: dict) -> bool:
        """Process payment and add to buffer instead of immediate save"""

        processor_type = self.health_manager.choose_best_processor()

        if await self._send_payment(payment, processor_type):
            processed_payment = ProcessedPayment(processor=processor_type, **payment)
            await self.payment_buffer.add_payment(processed_payment)
            return True

        alternative = "fallback" if processor_type == "default" else "default"
        if await self._send_payment(payment, alternative):
            processed_payment = ProcessedPayment(processor=alternative, **payment)
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

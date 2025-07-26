# src/payment_buffer.py
import asyncio
import logging
from datetime import datetime, timezone
from typing import List, TYPE_CHECKING

from src.schemas import ProcessedPayment

if TYPE_CHECKING:
    from src.worker import PaymentRepo

class PaymentBuffer:
    def __init__(self, repo: "PaymentRepo", batch_size=200, flush_interval=5):
        self.repo = repo
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.buffer: List[ProcessedPayment] = []
        self.last_flush = datetime.now(timezone.utc)
        self.lock = asyncio.Lock()

    async def add_payment(self, payment: ProcessedPayment):
        """Add payment to buffer, flush if needed"""
        async with self.lock:
            self.buffer.append(payment)

            # Check if we should flush
            should_flush = (
                    len(self.buffer) >= self.batch_size or  # Buffer full
                    (datetime.now(timezone.utc) - self.last_flush).total_seconds() > self.flush_interval
            )

            if should_flush:
                await self._flush()

    async def _flush(self):
        """Flush buffer to database"""
        if not self.buffer:
            return

        payments_to_save = self.buffer.copy()
        self.buffer.clear()
        self.last_flush = datetime.now(timezone.utc)

        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(
                None,
                self.repo.save_batch,
                payments_to_save
            )
            logging.info(f"Flushed {len(payments_to_save)} payments to database")
        except Exception as e:
            logging.error(f"Error flushing payments: {e}")
            async with self.lock:
                self.buffer.extend(payments_to_save)

    async def force_flush(self):
        """Force flush all buffered payments"""
        async with self.lock:
            await self._flush()

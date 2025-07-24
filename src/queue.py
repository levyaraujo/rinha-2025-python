# src/payment_queue.py
import asyncio
from typing import Dict, List
import logging
from datetime import datetime, timezone


class GlobalPaymentQueue:
    def __init__(self):
        self.queue = asyncio.Queue(maxsize=10000)
        self.processing = False
        self.failed_payments = asyncio.Queue(maxsize=1000)
        self.retry_count = {}

    async def add_payment(self, payment: dict):
        try:
            self.queue.put_nowait(payment)
        except asyncio.QueueFull:
            logging.warning(f"Queue full, dropping payment {payment.get('correlationId')}")

    async def start_processing(self, processor):
        if self.processing:
            return
        self.processing = True

        # Start multiple workers
        workers = [
            asyncio.create_task(self._worker(processor, i))
            for i in range(10)
        ]

        # Start retry worker
        retry_worker = asyncio.create_task(self._retry_worker(processor))

        await asyncio.gather(*workers, retry_worker)

    async def _worker(self, processor, worker_id: int):
        while True:
            try:
                # Use timeout to prevent hanging
                payment = await asyncio.wait_for(
                    self.queue.get(), timeout=1.0
                )
                await processor.process_single_payment(payment)
                self.queue.task_done()
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logging.error(f"Worker {worker_id} error: {e}")
                # Add to retry queue if not too many retries
                correlation_id = payment.get('correlationId', 'unknown')
                if self.retry_count.get(correlation_id, 0) < 3:
                    await self.failed_payments.put(payment)
                    self.retry_count[correlation_id] = self.retry_count.get(correlation_id, 0) + 1

    async def _retry_worker(self, processor):
        while True:
            try:
                payment = await asyncio.wait_for(
                    self.failed_payments.get(), timeout=1.0
                )
                await asyncio.sleep(1)  # Brief delay before retry
                await processor.process_single_payment(payment)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logging.error(f"Retry worker error: {e}")

    async def drain_queue(self, timeout_seconds: float = 10.0) -> bool:
        """Wait for all queued payments to be processed"""
        try:
            # Wait for queue to be empty with timeout
            await asyncio.wait_for(self.queue.join(), timeout=timeout_seconds)
            return True
        except asyncio.TimeoutError:
            logging.warning(f"Queue drain timeout after {timeout_seconds}s, {self.queue.qsize()} items remaining")
            return False
    
    def queue_size(self) -> int:
        """Get current queue size"""
        return self.queue.qsize()
    
    def retry_queue_size(self) -> int:
        """Get current retry queue size"""
        return self.failed_payments.qsize()


payment_queue: GlobalPaymentQueue = GlobalPaymentQueue()
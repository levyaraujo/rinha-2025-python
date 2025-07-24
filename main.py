import traceback
from datetime import timezone, datetime
from typing import Optional

from fastapi import Depends, FastAPI
from contextlib import asynccontextmanager
import asyncio
import logging

from fastapi.params import Param, Query

from src.db import create_tables, get_db
from src.health_checker import HealthChecker
from src.queue import payment_queue
from src.schemas import Payment, PaymentSummary, PaymentReport
from src.worker import Cache, PaymentApi, PaymentProcessor, PaymentRepo

logging.basicConfig(level=logging.INFO)


# Global processor for access in endpoints
global_processor = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global global_processor
    create_tables()

    cache = Cache()
    health_manager = HealthChecker(cache)
    repo = PaymentRepo()
    global_processor = PaymentProcessor(health_manager, repo)

    processing_task = asyncio.create_task(
        payment_queue.start_processing(global_processor)
    )

    # Start periodic health checks
    health_task = asyncio.create_task(periodic_health_check(health_manager))

    yield

    # Ensure all payments are processed before shutdown
    await global_processor.shutdown()
    processing_task.cancel()
    health_task.cancel()

async def periodic_health_check(health_manager):
    """Periodic health check to warm cache"""
    while True:
        try:
            await health_manager._check_health_async("default")
            await health_manager._check_health_async("fallback")
            await asyncio.sleep(5)
        except Exception as e:
            logging.error(f"Health check error: {e}")
            await asyncio.sleep(5)

def get_cache():
    return Cache()


app = FastAPI(lifespan=lifespan)

@app.post("/payments")
async def create_payment(payment: Payment):
    """Optimized payment endpoint"""
    try:
        await payment_queue.add_payment(payment.to_dict())
        return {"message": "Payment queued"}
    except Exception as e:
        logging.error(f"Error queueing payment: {e}")
        return {"error": "Failed to queue payment"}


@app.get("/payments-summary", response_model=PaymentReport)
async def summary(to: Optional[str] = Query(None, alias="to"), from_date: Optional[str] = Query(None, alias="from")):
    """Generate payment summary with guaranteed consistency"""
    global global_processor
    
    # 1. Drain the queue to ensure all payments are being processed
    queue_drained = await payment_queue.drain_queue(timeout_seconds=15.0)
    if not queue_drained:
        logging.warning(f"Queue not fully drained: {payment_queue.queue_size()} items remaining")
    
    # 2. Force flush all buffered payments to ensure they're saved
    if global_processor:
        await global_processor.payment_buffer.force_flush()
    
    # Small delay to ensure database writes are committed
    await asyncio.sleep(0.1)
    
    # 3. Get all payments from database
    repo = PaymentRepo()
    payments = repo.get_all()
    
    # 4. Apply date filtering (crucial for K6 test)
    to_dt = datetime.fromisoformat(to.replace("Z", "+00:00")) if to else datetime.now(timezone.utc)
    from_dt = datetime.fromisoformat(from_date.replace("Z", "+00:00")) if from_date else datetime.min.replace(
        tzinfo=timezone.utc)

    # Filter by date range and processor
    default = [payment for payment in payments 
               if payment.processor == "default" 
               and from_dt <= payment.requestedAt <= to_dt]
    fallback = [payment for payment in payments 
                if payment.processor == "fallback" 
                and from_dt <= payment.requestedAt <= to_dt]

    default_summary = PaymentSummary(
        totalRequests=len(default),
        totalAmount=sum(payment.amount for payment in default),
    )

    fallback_summary = PaymentSummary(
        totalRequests=len(fallback),
        totalAmount=sum(payment.amount for payment in fallback),
    )

    logging.info(f"Summary: Default={len(default)} payments (${sum(payment.amount for payment in default)}), "
                f"Fallback={len(fallback)} payments (${sum(payment.amount for payment in fallback)})")

    return PaymentReport(
        default=default_summary,
        fallback=fallback_summary
    )


@app.post("/purge-payments")
async def purge_payments():
    repo = PaymentRepo()
    repo.purge()
    return {"message": "Payments purged"}, 200

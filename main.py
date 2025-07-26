from datetime import timezone, datetime
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.params import Query

from src.db import create_tables
from src.health_checker import HealthChecker
from src.queue import payment_queue
from src.schemas import Payment, PaymentSummary, PaymentReport
from src.worker import Cache, PaymentProcessor, PaymentRepo

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()

    cache = Cache()
    health_manager = HealthChecker(cache)
    repo = PaymentRepo()
    processor = PaymentProcessor(health_manager, repo)

    processing_task = asyncio.create_task(
        payment_queue.start_processing(processor)
    )

    health_task = asyncio.create_task(periodic_health_check(health_manager))

    yield

    await processor.shutdown()
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
def summary(to: Optional[str] = Query(None, alias="to"), from_date: Optional[str] = Query(None, alias="from")):
    repo = PaymentRepo()
    payments = repo.get_all()
    to = datetime.fromisoformat(to.replace("Z", "+00:00")) if to else datetime.now(timezone.utc)
    from_date = datetime.fromisoformat(from_date.replace("Z", "+00:00")) if from_date else datetime.min.replace(
        tzinfo=timezone.utc)

    default = [payment for payment in payments if payment.processor == "default"]
    fallback = [payment for payment in payments if payment.processor == "fallback"]

    default_summary = PaymentSummary(
        totalRequests=len(default),
        totalAmount=sum(payment.amount for payment in default),
    )

    fallback_summary = PaymentSummary(
        totalRequests=len(fallback),
        totalAmount=sum(payment.amount for payment in fallback),
    )

    return PaymentReport(
        default=default_summary,
        fallback=fallback_summary
    )


@app.post("/purge-payments")
async def purge_payments():
    repo = PaymentRepo()
    repo.purge()
    return {"message": "Payments purged"}, 200

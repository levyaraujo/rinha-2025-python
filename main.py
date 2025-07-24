import traceback
from datetime import timezone, datetime
from typing import Optional

from fastapi import Depends, FastAPI
from contextlib import asynccontextmanager
import asyncio
import logging

from fastapi.params import Param, Query

from src.db import create_tables, get_db
from src.schemas import Payment, PaymentSummary, PaymentReport
from src.worker import HealthChecker, Cache, PaymentApi, PaymentProcessor, PaymentRepo

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    task = asyncio.create_task(health_checker())
    yield
    task.cancel()


def get_cache():
    return Cache()


app = FastAPI(lifespan=lifespan)


async def health_checker():
    cache = Cache()
    health = HealthChecker(cache)
    while True:
        try:
            health.check_health_default()
            health.check_health_fallback()
        except Exception as e:
            logging.error(f"Error checking health: {e}")
        await asyncio.sleep(5)


@app.post("/payments")
async def create_payment(payment: Payment, cache: Cache = Depends(get_cache)):
    try:
        repo = PaymentRepo()
        worker = PaymentProcessor(cache, PaymentApi(cache), repo)
        await worker.put(payment.to_dict())
        await worker.process()
    except:
        traceback.print_exc()

    return {"message": "Payment created"}, 201


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

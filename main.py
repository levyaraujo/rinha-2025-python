from fastapi import FastAPI
from contextlib import asynccontextmanager
import asyncio
import logging

from src.worker import HealthChecker, Cache

logging.basicConfig(level=logging.INFO)

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(health_checker())
    yield
    task.cancel()

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
def create_payment():
    return {"message": "Payment created"}
import logging
import os
from asyncio import Queue

import httpx
import redis
import json
import traceback

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


class HealthChecker:
    def __init__(self, cache: Cache):
        self.__default_payment_processor = os.getenv("DEFAULT_PAYMENT_PROCESSOR")
        self.__fallback_payment_processor = os.getenv("FALLBACK_PAYMENT_PROCESSOR")
        self.cache = cache

    def check_health_default(self):
        health_url = f"{self.__default_payment_processor}/payments/service-health"
        try:
            response = httpx.get(health_url)
            response.raise_for_status()
            status = response.json()
            self.cache.set("health_default", json.dumps(status))
        except httpx.RequestError:
            status = {"failing": True, "minResponseTime": float("inf")}
            self.cache.set("health_default", json.dumps(status))

    def check_health_fallback(self):
        health_url = f"{self.__fallback_payment_processor}/payments/service-health"
        try:
            response = httpx.get(health_url)
            response.raise_for_status()
            status = response.json()
            self.cache.set("health_fallback", json.dumps(status))
        except httpx.RequestError:
            status = {"failing": True, "minResponseTime": float("inf")}
            self.cache.set("health_fallback", json.dumps(status))


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
    def __init__(self, cache: Cache, api: PaymentApi, repo: PaymentRepo):
        self.cache = cache
        self.queue = Queue()
        self.api = api
        self.repo = repo
    
    async def put(self, payment: dict):
        await self.queue.put(payment)

    async def process(self) -> ProcessedPayment | None:
        while not self.queue.empty():
            payment = await self.queue.get()
            try:
                health_default = json.loads(self.cache.get("health_default") or '{"failing": true}')
                health_fallback = json.loads(self.cache.get("health_fallback") or '{"failing": true}')


                if not health_default["failing"]:
                    try:
                        status = await self.api.send_payment_default(payment)
                        logging.info(f"Tentativa default para {payment['correlationId']}: {status}")
                        
                        if status == 422:
                            logging.warning(f"Payment {payment['correlationId']} already exists or invalid")
                            self.queue.task_done()
                            continue
                        
                        if status == 200:
                            self.repo.save(ProcessedPayment(processor="default", **payment))
                            logging.info(f"Salvou {payment['correlationId']} via default")
                            self.queue.task_done()
                            continue
                    except Exception as e:
                        traceback.print_exc()
                        logging.error(f"Error sending to default processor: {e}")
                
                if not health_fallback["failing"]:
                    try:
                        status = await self.api.send_payment_fallback(payment)
                        logging.info(f"Tentativa fallback para {payment['correlationId']}: {status}")
                        
                        if status == 422:
                            logging.warning(f"Payment {payment['correlationId']} already exists or invalid")
                            self.queue.task_done()
                            continue
                        
                        if status == 200:
                            self.repo.save(ProcessedPayment(processor="fallback", **payment))
                            logging.info(f"Salvou {payment['correlationId']} via fallback")
                            self.queue.task_done()
                            continue
                    except Exception as e:
                        logging.error(f"Error sending to fallback processor: {e}")
                
                if health_default["minResponseTime"] < health_fallback["minResponseTime"]:
                    status = await self.api.send_payment_fallback(payment)

                
            except Exception as e:
                logging.error(f"Unexpected error processing payment {payment.get('correlationId', 'unknown')}: {e}")
                self.queue.task_done()
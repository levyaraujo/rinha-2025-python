import os
import httpx
import redis
import json

class Cache:
    def __init__(self):
        self.client = redis.Redis(host="cache", port=6379)

    def get(self, key: str):
        return self.client.get(key)
    
    def set(self, key: str, value: str):
        return self.client.set(key, value)

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
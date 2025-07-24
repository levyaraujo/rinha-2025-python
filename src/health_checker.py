import asyncio
import json
import time
from typing import Dict

import httpx

from src.worker import Cache


class HealthChecker:
    def __init__(self, cache: Cache):
        self.cache = cache
        self.last_check = {"default": 0, "fallback": 0}
        self.health_data = {
            "default": {"failing": True, "minResponseTime": float("inf")},
            "fallback": {"failing": True, "minResponseTime": float("inf")}
        }
        self.check_interval = 5  # seconds

    async def get_health_status(self, processor_type: str) -> Dict:
        """Get cached health status, check if stale"""
        now = time.time()
        if now - self.last_check[processor_type] > self.check_interval:
            asyncio.create_task(self._check_health_async(processor_type))

        return self.health_data[processor_type]

    async def _check_health_async(self, processor_type: str):
        """Async health check that updates cache"""
        if processor_type == "default":
            url = "http://payment-processor-default:8080/payments/service-health"
        else:
            url = "http://payment-processor-fallback:8080/payments/service-health"

        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    self.health_data[processor_type] = response.json()
                else:
                    self.health_data[processor_type] = {
                        "failing": True,
                        "minResponseTime": float("inf")
                    }
        except Exception:
            self.health_data[processor_type] = {
                "failing": True,
                "minResponseTime": float("inf")
            }

        self.last_check[processor_type] = time.time()

        # Update Redis cache
        self.cache.set(f"health_{processor_type}",
                       json.dumps(self.health_data[processor_type]))

    def choose_best_processor(self) -> str:
        """Choose the best processor based on health status"""
        default_health = self.health_data["default"]
        fallback_health = self.health_data["fallback"]

        if (not default_health["failing"] and
                (fallback_health["failing"] or
                 default_health["minResponseTime"] <= fallback_health["minResponseTime"])):
            return "default"
        elif not fallback_health["failing"]:
            return "fallback"
        else:
            return "default"

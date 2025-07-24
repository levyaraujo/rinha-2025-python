from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from uuid import UUID
from pydantic import BaseModel

class Payment(BaseModel):
    correlationId: UUID
    amount: float
    requestedAt: datetime = datetime.now(tz=timezone.utc)

    def to_dict(self) -> dict:
        return {
            "correlationId": str(self.correlationId),
            "amount": self.amount,
            "requestedAt": self.requestedAt.isoformat()
        }

class ProcessedPayment(BaseModel):
    correlationId: UUID
    processor: str
    amount: float
    requestedAt: datetime

    def to_dict(self) ->  dict:
        return {
            "correlationId": str(self.correlationId),
            "processor": self.processor,
            "amount": self.amount,
            "requestedAt": self.requestedAt.isoformat()
        }

    class Config:
        from_attributes = True

class PaymentSummary(BaseModel):
    totalRequests: int
    totalAmount: float

class PaymentReport(BaseModel):
    default: PaymentSummary
    fallback: PaymentSummary
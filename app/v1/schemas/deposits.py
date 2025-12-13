from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from ...utils.enums import DepositStatus

class DepositIntentCreate(BaseModel):
    amount: float = Field(gt=0)
    currency: str = "USD"
    payment_method: str = "card"
    provider: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class DepositIntentOut(BaseModel):
    id: str
    amount: float
    currency: str
    payment_method: str
    provider: Optional[str] = None
    provider_reference: Optional[str] = None
    payment_url: Optional[str] = None
    status: DepositStatus
    metadata: Optional[Dict[str, Any]] = None
    confirmed_amount: Optional[float] = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_orm_row(cls, row):
        return cls(
            id=row.id,
            amount=row.amount,
            currency=row.currency,
            payment_method=row.payment_method,
            provider=row.provider,
            provider_reference=row.provider_reference,
            payment_url=row.payment_url,
            status=row.status,
            metadata=row.metadata_ if hasattr(row, "metadata_") else None,
            confirmed_amount=row.confirmed_amount,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from ...utils.enums import WithdrawalStatus

class WithdrawalRequestCreate(BaseModel):
    amount: float = Field(gt=0)
    currency: str = "USD"

    bank_code: Optional[str] = None
    bank_name: Optional[str] = None
    account_type: Optional[str] = None
    clabe: Optional[str] = None
    account_holder: Optional[str] = None

    email: Optional[str] = None
    phone: Optional[str] = None
    concept: Optional[str] = None

    investment_id: Optional[str] = None

    preview_snapshot: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None

class WithdrawalRequestOut(BaseModel):
    id: str
    amount: float
    currency: str

    bank_code: Optional[str] = None
    bank_name: Optional[str] = None
    account_type: Optional[str] = None
    clabe: Optional[str] = None
    account_holder: Optional[str] = None

    email: Optional[str] = None
    phone: Optional[str] = None
    concept: Optional[str] = None

    status: WithdrawalStatus

    preview_snapshot: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None

    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None

    created_at: datetime
    updated_at: datetime

    # For UI compatibility (optional): derived reference
    reference: Optional[str] = None

    @classmethod
    def from_orm_row(cls, row):
        ref = None
        if getattr(row, "metadata_", None):
            ref = row.metadata_.get("stripe_transfer_id")
        return cls(
            id=row.id,
            amount=float(row.amount),
            currency=row.currency,

            bank_code=row.bank_code,
            bank_name=row.bank_name,
            account_type=row.account_type,
            clabe=row.clabe,
            account_holder=row.account_holder,

            email=row.email,
            phone=row.phone,
            concept=row.concept,

            status=row.status,

            preview_snapshot=row.preview_snapshot,
            metadata=row.metadata_,

            reviewed_by=row.reviewed_by,
            reviewed_at=row.reviewed_at,

            created_at=row.created_at,
            updated_at=row.updated_at,
            reference=ref,
        )

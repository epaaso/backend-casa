from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from ...utils.enums import KYCStatus


class KYCStartRequest(BaseModel):
    provider: Optional[str] = "sumsub"


class KYCSessionResponse(BaseModel):
    provider: str
    session_id: str
    redirect_url: Optional[str] = None

    # opcional (si luego quieres SDK token)
    access_token: Optional[str] = None
    sdk_url: Optional[str] = None


class KYCStatusResponse(BaseModel):
    status: KYCStatus
    updatedAt: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # extras tipo el doc
    provider: Optional[str] = None
    session_id: Optional[str] = None
    verified_at: Optional[datetime] = None
    reason: Optional[str] = None
    verification_level: Optional[str] = None

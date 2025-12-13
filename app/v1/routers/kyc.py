import os
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Query

from sqlalchemy.ext.asyncio import AsyncSession
from ...db import get_session
from ...utils.enums import KYCStatus
from ..schemas.kyc import KYCStartRequest, KYCSessionResponse, KYCStatusResponse
from ..repositories.kyc import KYCRepository
from ...services.kyc_providers.factory import get_kyc_provider

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/kyc", tags=["KYC"])  # parent /v1 is added by app/v1/api.py


def _resolve_client_id(clientId: str | None, x_client_id: str | None) -> str:
    return clientId or x_client_id or "demo-client-1"


def _sandbox() -> bool:
    return os.getenv("DEBUG", "0") == "1" or os.getenv("TESTING", "0") == "1"


@router.post("/start", response_model=KYCSessionResponse)
async def start_kyc(
    payload: KYCStartRequest,
    clientId: str | None = Query(default=None),
    x_client_id: str | None = Header(default=None, alias="X-Client-Id"),
    db: AsyncSession = Depends(get_session),
):
    client_id = _resolve_client_id(clientId, x_client_id)
    provider_name = (payload.provider or "sumsub").lower()
    provider = get_kyc_provider(provider_name)

    # Idempotency: reuse last pending if exists
    repo = KYCRepository(db)
    existing = await repo.get_latest_for_client(client_id)
    if existing and existing.status in (KYCStatus.PENDING.value,):
        return KYCSessionResponse(provider=existing.provider, session_id=existing.session_id, redirect_url=None)

    # Create applicant/session with provider
    applicant = await provider.create_applicant(client_id=client_id, user_data={"client_id": client_id})
    session_id = applicant.get("applicantId") or applicant.get("session_id")
    if not session_id:
        raise HTTPException(status_code=500, detail="KYC provider did not return applicantId")

    access_token = None
    sdk_url = None
    redirect_url = None

    try:
        access_token = await provider.get_access_token(session_id)
        sdk_url = "https://sdk.sumsub.com"
        redirect_url = f"{os.getenv('FRONTEND_URL','http://localhost:5173')}/kyc?session_id={session_id}"
    except Exception:
        redirect_url = f"{os.getenv('FRONTEND_URL','http://localhost:5173')}/kyc?session_id={session_id}"

    ver = await repo.create_verification({
        "client_id": client_id,
        "session_id": session_id,
        "provider": provider_name,
        "status": KYCStatus.PENDING.value,
        "verification_level": os.getenv("SUMSUB_LEVEL_NAME"),
        "provider_data": applicant,
        "document_types": None,
        "verified_at": None,
    })
    await db.commit()
    await db.refresh(ver)

    return KYCSessionResponse(
        provider=provider_name,
        session_id=session_id,
        redirect_url=redirect_url,
        access_token=access_token,
        sdk_url=sdk_url,
    )


@router.get("/status", response_model=KYCStatusResponse)
async def kyc_status(
    clientId: str | None = Query(default=None),
    x_client_id: str | None = Header(default=None, alias="X-Client-Id"),
    db: AsyncSession = Depends(get_session),
):
    client_id = _resolve_client_id(clientId, x_client_id)
    repo = KYCRepository(db)
    ver = await repo.get_latest_for_client(client_id)
    if not ver:
        return KYCStatusResponse(status=KYCStatus.PENDING, updatedAt=None, updated_at=None, provider=None, session_id=None)

    return KYCStatusResponse(
        status=ver.status,
        updatedAt=ver.updated_at,
        updated_at=ver.updated_at,
        provider=ver.provider,
        session_id=ver.session_id,
        verified_at=ver.verified_at,
        reason=ver.reason,
        verification_level=ver.verification_level,
    )


@router.post("/webhook")
async def kyc_webhook(
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: AsyncSession = Depends(get_session),
):
    payload = await request.json()
    event_type = payload.get("type") or payload.get("eventType") or "unknown"

    logger.info(f"[KYC WEBHOOK] type={event_type} idempotency={idempotency_key}")

    provider_name = (payload.get("provider") or "sumsub").lower()
    provider = get_kyc_provider(provider_name)

    normalized = await provider.process_webhook(payload)
    session_id = normalized.get("session_id")
    if not session_id:
        return {"status": "ignored", "reason": "missing_session_id"}

    repo = KYCRepository(db)
    ver = await repo.get_by_session_id(session_id)
    if not ver:
        return {"status": "error", "message": "KYC verification not found"}

    ver.status = normalized.get("status") or KYCStatus.PENDING.value
    ver.reason = normalized.get("reason")
    ver.provider_data = normalized.get("provider_data") or payload
    if normalized.get("verification_level"):
        ver.verification_level = normalized["verification_level"]
    if normalized.get("document_types"):
        ver.document_types = normalized["document_types"]

    if ver.status == KYCStatus.APPROVED.value:
        ver.verified_at = datetime.now(timezone.utc)

    await repo.create_webhook_event({
        "kyc_verification_id": ver.id,
        "event_type": event_type,
        "raw_payload": payload,
        "processed": True,
    })

    await db.commit()
    return {"status": "success"}

import uuid
from ...utils.enums import KYCStatus
from .base import KYCProvider


class SumsubKYCProvider(KYCProvider):
    """Minimal Sumsub-like provider for structure compatibility.

    For MVP, we don't call external APIs; we simulate responses and rely on webhook to update status.
    In production, replace methods to perform real HTTP requests and signature validation as needed.
    """

    async def create_applicant(self, *, client_id: str, user_data: dict):
        # Simulate Sumsub applicant creation
        return {"applicantId": f"sumsub_{uuid.uuid4()}"}

    async def get_access_token(self, applicant_id: str) -> str:
        # Simulate access token (SDK)
        return f"sumsub_token_{applicant_id}"

    async def get_applicant_status(self, applicant_id: str):
        # Default pending until webhook updates
        return {"reviewStatus": "pending"}

    async def process_webhook(self, payload: dict):
        review = payload.get("review") or {}
        review_status = payload.get("reviewStatus") or review.get("reviewStatus") or "pending"
        reason = review.get("moderationComment") or payload.get("reason")
        mapping = {
            "completed": KYCStatus.APPROVED.value,
            "pending": KYCStatus.PENDING.value,
            "queued": KYCStatus.PENDING.value,
            "rejected": KYCStatus.REJECTED.value,
            "onHold": KYCStatus.PENDING.value,
            "finalRejected": KYCStatus.REJECTED.value,
            "expired": KYCStatus.EXPIRED.value,
        }
        return {
            "session_id": payload.get("applicantId") or payload.get("applicant_id") or payload.get("applicant"),
            "status": mapping.get(review_status, KYCStatus.PENDING.value),
            "reason": reason,
            "provider_data": payload,
        }

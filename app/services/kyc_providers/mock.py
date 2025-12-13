import uuid
from datetime import datetime, timezone
from ...utils.enums import KYCStatus
from .base import KYCProvider


class MockKYCProvider(KYCProvider):
    async def create_applicant(self, *, client_id: str, user_data: dict):
        return {"applicantId": f"mock_{uuid.uuid4()}", "createdAt": datetime.now(timezone.utc).isoformat()}

    async def get_access_token(self, applicant_id: str) -> str:
        return f"mock_token_{applicant_id}"

    async def get_applicant_status(self, applicant_id: str):
        return {"reviewStatus": "pending"}

    async def process_webhook(self, payload: dict):
        # Accept payload similar to Sumsub test
        review_status = payload.get("reviewStatus") or payload.get("review", {}).get("reviewStatus") or "pending"
        mapping = {
            "completed": KYCStatus.APPROVED.value,
            "pending": KYCStatus.PENDING.value,
            "queued": KYCStatus.PENDING.value,
            "rejected": KYCStatus.REJECTED.value,
            "onHold": KYCStatus.PENDING.value,
        }
        return {
            "session_id": payload.get("applicantId") or payload.get("applicant_id"),
            "status": mapping.get(review_status, KYCStatus.PENDING.value),
            "reason": payload.get("reason"),
            "provider_data": payload,
        }

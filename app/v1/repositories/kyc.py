from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ...models import KYCVerification, KYCWebhookEvent


class KYCRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_latest_for_client(self, client_id: str) -> KYCVerification | None:
        stmt = (
            select(KYCVerification)
            .where(KYCVerification.client_id == client_id)
            .order_by(KYCVerification.created_at.desc())
        )
        return (await self.db.execute(stmt)).scalars().first()

    async def get_by_session_id(self, session_id: str) -> KYCVerification | None:
        stmt = select(KYCVerification).where(KYCVerification.session_id == session_id)
        return (await self.db.execute(stmt)).scalars().first()

    async def create_verification(self, data: dict) -> KYCVerification:
        obj = KYCVerification(**data)
        self.db.add(obj)
        await self.db.flush()
        return obj

    async def create_webhook_event(self, data: dict) -> KYCWebhookEvent:
        obj = KYCWebhookEvent(**data)
        self.db.add(obj)
        await self.db.flush()
        return obj

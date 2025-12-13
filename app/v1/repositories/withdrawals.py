from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ...models import WithdrawalRequest

class WithdrawalRequestRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, data: dict) -> WithdrawalRequest:
        obj = WithdrawalRequest(**data)
        self.db.add(obj)
        await self.db.flush()
        return obj

    async def list_for_client(self, client_id: str, limit: int, offset: int) -> list[WithdrawalRequest]:
        stmt = (
            select(WithdrawalRequest)
            .where(WithdrawalRequest.client_id == client_id)
            .order_by(WithdrawalRequest.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def get_by_id(self, withdrawal_id: str, client_id: str) -> WithdrawalRequest | None:
        stmt = select(WithdrawalRequest).where(
            WithdrawalRequest.id == withdrawal_id,
            WithdrawalRequest.client_id == client_id,
        )
        return (await self.db.execute(stmt)).scalars().first()

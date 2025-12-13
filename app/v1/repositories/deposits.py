from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ...models import DepositIntent

class DepositIntentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, data: dict) -> DepositIntent:
        obj = DepositIntent(**data)
        self.db.add(obj)
        await self.db.flush()
        return obj

    async def list_for_client(self, client_id: str, limit: int, offset: int) -> list[DepositIntent]:
        stmt = (
            select(DepositIntent)
            .where(DepositIntent.client_id == client_id)
            .order_by(DepositIntent.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def get_by_id(self, deposit_id: str, client_id: str) -> DepositIntent | None:
        stmt = select(DepositIntent).where(
            DepositIntent.id == deposit_id,
            DepositIntent.client_id == client_id,
        )
        return (await self.db.execute(stmt)).scalars().first()

    async def get_by_id_no_owner(self, deposit_id: str) -> DepositIntent | None:
        stmt = select(DepositIntent).where(DepositIntent.id == deposit_id)
        return (await self.db.execute(stmt)).scalars().first()

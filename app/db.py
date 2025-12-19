import os

from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy import text

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./app.db")

# Issue #5: Make connect_args conditional for database portability
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_async_engine(
    DATABASE_URL,
    connect_args=connect_args,
    future=True,
)
AsyncSessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


class Base(DeclarativeBase):
    pass


async def init_db():
    """Create tables at startup using the async engine. Includes lightweight migrations for MVP."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Lightweight migration: add orders.reject_reason if missing (SQLite pragma-based check)
        try:
            res = await conn.execute(text("PRAGMA table_info(orders);"))
            cols = [row[1] for row in res.fetchall()]
            if "reject_reason" not in cols:
                await conn.execute(text("ALTER TABLE orders ADD COLUMN reject_reason VARCHAR NULL;"))
            # Issue #3: Add venue ID columns for future Centroid/FIX integration
            if "cl_ord_id" not in cols:
                await conn.execute(text("ALTER TABLE orders ADD COLUMN cl_ord_id VARCHAR NULL;"))
            if "orig_cl_ord_id" not in cols:
                await conn.execute(text("ALTER TABLE orders ADD COLUMN orig_cl_ord_id VARCHAR NULL;"))
            if "venue_order_id" not in cols:
                await conn.execute(text("ALTER TABLE orders ADD COLUMN venue_order_id VARCHAR NULL;"))
            if "last_exec_id" not in cols:
                await conn.execute(text("ALTER TABLE orders ADD COLUMN last_exec_id VARCHAR NULL;"))
        except Exception as e:
            # Ignore migration errors in MVP; table may not exist yet or DB may not support PRAGMA
            print(f"[init_db] migration check failed or skipped: {e}")

        # Lightweight migration: ensure deposit_intents columns exist (SQLite)
        try:
            res = await conn.execute(text("PRAGMA table_info(deposit_intents);"))
            cols = [row[1] for row in res.fetchall()]
            # Example future-proofing; uncomment if migrating existing DBs without drop
            # expected_cols = {
            #     "id", "client_id", "amount", "currency", "payment_method",
            #     "provider", "provider_reference", "payment_url", "status",
            #     "metadata", "confirmed_amount", "created_at", "updated_at"
            # }
            # for col in expected_cols - set(cols):
            #     if col == "metadata":
            #         await conn.execute(text("ALTER TABLE deposit_intents ADD COLUMN metadata JSON NULL;"))
            #     elif col in ("confirmed_amount",):
            #         await conn.execute(text("ALTER TABLE deposit_intents ADD COLUMN confirmed_amount FLOAT NULL;"))
            #     elif col in ("provider", "provider_reference", "payment_url"):
            #         await conn.execute(text(f"ALTER TABLE deposit_intents ADD COLUMN {col} VARCHAR NULL;"))
            #     elif col in ("updated_at",):
            #         await conn.execute(text("ALTER TABLE deposit_intents ADD COLUMN updated_at DATETIME NULL;"))
            #     # other columns would require more complex migrations; for dev, prefer recreating DB
        except Exception as e:
            print(f"[init_db] deposit_intents migration skipped: {e}")


async def get_session():
    async with AsyncSessionLocal() as session:
        yield session

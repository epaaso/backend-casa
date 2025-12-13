import uuid
from datetime import datetime
from sqlalchemy import String, Float, DateTime, ForeignKey, Boolean, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base

# ------------------------------
# Fase 2 — Nuevos modelos
# ------------------------------

class Order(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    client_id: Mapped[str] = mapped_column(String, index=True)
    symbol: Mapped[str] = mapped_column(String, index=True)
    side: Mapped[str] = mapped_column(String)
    type: Mapped[str] = mapped_column(String)
    qty: Mapped[float] = mapped_column(Float)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    time_in_force: Mapped[str] = mapped_column(String, default="GTC")

    status: Mapped[str] = mapped_column(String, default="NEW", index=True)
    cum_qty: Mapped[float] = mapped_column(Float, default=0.0)
    avg_px: Mapped[float | None] = mapped_column(Float, nullable=True)
    reject_reason: Mapped[str | None] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    executions: Mapped[list["Execution"]] = relationship("Execution", back_populates="order", cascade="all, delete-orphan")

class Execution(Base):
    __tablename__ = "executions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    order_id: Mapped[str] = mapped_column(String, ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    exec_qty: Mapped[float] = mapped_column(Float)
    exec_px: Mapped[float] = mapped_column(Float)
    exec_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    order: Mapped[Order] = relationship("Order", back_populates="executions")

# Fase 2.1 — Tabla de límites de riesgo
class RiskLimit(Base):
    __tablename__ = "risk_limits"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    client_id: Mapped[str] = mapped_column(String, index=True)
    symbol: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    max_notional: Mapped[float] = mapped_column(Float)
    max_order_size: Mapped[float] = mapped_column(Float)
    trading_hours: Mapped[str] = mapped_column(String)  # formato "HH:MM-HH:MM"
    blocked: Mapped[bool] = mapped_column(Boolean, default=False)


# ------------------------------
# Fase 3 — Ledger mínimo (Deposits/Withdrawals)
# ------------------------------
class Deposit(Base):
    __tablename__ = "deposits"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    client_id: Mapped[str] = mapped_column(String, index=True)
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String, default="USD")
    payment_method: Mapped[str | None] = mapped_column(String, nullable=True)
    provider: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Withdrawal(Base):
    __tablename__ = "withdrawals"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    client_id: Mapped[str] = mapped_column(String, index=True)
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String, default="USD")
    status: Mapped[str] = mapped_column(String, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class WithdrawalRequest(Base):
    __tablename__ = "withdrawal_requests"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # En tu backend no hay user_id. Usamos client_id (equivalente al "owner").
    client_id: Mapped[str] = mapped_column(String, index=True)

    # inversión relacionada (opcional)
    investment_id: Mapped[str | None] = mapped_column(String, nullable=True)

    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String, default="USD")

    bank_code: Mapped[str | None] = mapped_column(String, nullable=True)
    bank_name: Mapped[str | None] = mapped_column(String, nullable=True)
    account_type: Mapped[str | None] = mapped_column(String, nullable=True)
    clabe: Mapped[str | None] = mapped_column(String, nullable=True)
    account_holder: Mapped[str | None] = mapped_column(String, nullable=True)

    email: Mapped[str | None] = mapped_column(String, nullable=True)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    concept: Mapped[str | None] = mapped_column(String, nullable=True)

    status: Mapped[str] = mapped_column(String, default="pending_review", index=True)

    preview_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Igual que el ejemplo: columna en DB se llama "metadata", atributo en modelo metadata_
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)

    reviewed_by: Mapped[str | None] = mapped_column(String, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ------------------------------
# Deposit Intents (for payments)
# ------------------------------
class DepositIntent(Base):
    __tablename__ = "deposit_intents"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    client_id: Mapped[str] = mapped_column(String, index=True)

    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String, default="USD")
    payment_method: Mapped[str] = mapped_column(String, default="card")

    provider: Mapped[str | None] = mapped_column(String, nullable=True)
    provider_reference: Mapped[str | None] = mapped_column(String, nullable=True)  # Stripe session id
    payment_url: Mapped[str | None] = mapped_column(String, nullable=True)         # Stripe checkout url

    status: Mapped[str] = mapped_column(String, default="pending", index=True)

    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    confirmed_amount: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ------------------------------
# KYC Models
# ------------------------------
class KYCVerification(Base):
    __tablename__ = "kyc_verifications"
    __table_args__ = (UniqueConstraint("session_id", name="uq_kyc_verifications_session"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # owner por client_id
    client_id: Mapped[str] = mapped_column(String, index=True)

    session_id: Mapped[str] = mapped_column(String, nullable=False)
    provider: Mapped[str] = mapped_column(String, nullable=False)

    status: Mapped[str] = mapped_column(String, default="pending", index=True)
    verification_level: Mapped[str | None] = mapped_column(String, nullable=True)
    reason: Mapped[str | None] = mapped_column(String, nullable=True)

    provider_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    document_types: Mapped[list | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class KYCWebhookEvent(Base):
    __tablename__ = "kyc_webhook_events"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    kyc_verification_id: Mapped[str] = mapped_column(String, ForeignKey("kyc_verifications.id", ondelete="CASCADE"), index=True)

    event_type: Mapped[str] = mapped_column(String, nullable=True)
    raw_payload: Mapped[dict] = mapped_column(JSON, nullable=False)

    processed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

from typing import Optional, Iterable
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..models import RiskLimit

# Fase 2.1 — Repositorio CRUD para risk_limits
class RiskLimitsRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, data: dict) -> RiskLimit:
        item = RiskLimit(**data)
        self.db.add(item)
        self.db.flush()
        return item

    def get(self, id_: str) -> Optional[RiskLimit]:
        return self.db.get(RiskLimit, id_)

    def list(self, client_id: Optional[str] = None, symbol: Optional[str] = None) -> list[RiskLimit]:
        stmt = select(RiskLimit)
        if client_id is not None:
            stmt = stmt.where(RiskLimit.client_id == client_id)
        if symbol is not None:
            stmt = stmt.where(RiskLimit.symbol == symbol)
        return list(self.db.execute(stmt).scalars().all())

    def by_client_symbol(self, client_id: str, symbol: str) -> Optional[RiskLimit]:
        """Preferir un límite específico por símbolo; si no hay, usar el general (symbol IS NULL)."""
        # Buscar límite específico
        stmt_specific = select(RiskLimit).where(
            RiskLimit.client_id == client_id,
            RiskLimit.symbol == symbol,
        )
        specific = self.db.execute(stmt_specific).scalars().first()
        if specific:
            return specific
        # Buscar límite general
        stmt_general = select(RiskLimit).where(
            RiskLimit.client_id == client_id,
            RiskLimit.symbol.is_(None),
        )
        return self.db.execute(stmt_general).scalars().first()

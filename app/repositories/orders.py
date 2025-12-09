from sqlalchemy import select
from sqlalchemy.orm import Session
from ..models import Order as OrderModel
from ..utils.enums import OrderStatus

class OrderRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, data: dict) -> OrderModel:
        order = OrderModel(**data)
        self.db.add(order)
        self.db.flush()  # assign id
        return order

    def get(self, order_id: str) -> OrderModel | None:
        return self.db.get(OrderModel, order_id)

    def list(self, client_id: str | None, symbol: str | None) -> list[OrderModel]:
        stmt = select(OrderModel)
        if client_id:
            stmt = stmt.where(OrderModel.client_id == client_id)
        if symbol:
            stmt = stmt.where(OrderModel.symbol == symbol)
        return list(self.db.execute(stmt).scalars().all())

    def save(self, order: OrderModel):
        self.db.add(order)

    def set_status(self, order: OrderModel, status: OrderStatus):
        order.status = status
        self.db.add(order)

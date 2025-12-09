
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from .db import session_scope, Base, engine
from .models import Order as OrderModel
from .schemas import OrderCreateRequest, Order as OrderSchema, Position as PositionSchema
from .repositories.orders import OrderRepository
from .repositories.positions import PositionsRepository
from .utils.enums import OrderStatus
from .services.fix_gateway import fix_gateway

router = APIRouter()

# Ensure tables exist (MVP)
Base.metadata.create_all(bind=engine)


def get_db():
    with session_scope() as s:
        yield s


@router.get("/health")
def health():
    return {"status": "OK"}


@router.post("/orders", response_model=OrderSchema, status_code=201)
def create_order(payload: OrderCreateRequest, db: Session = Depends(get_db)):
    """Create an order, persist it, commit it so FIX worker can see it,
    then enqueue FIX SEND event.
    """
    repo = OrderRepository(db)

    order = repo.create({
        "client_id": payload.clientId,
        "symbol": payload.symbol,
        "side": payload.side.value,
        "type": payload.type.value,
        "qty": payload.qty,
        "price": payload.price,
        "time_in_force": payload.timeInForce.value,
        "status": OrderStatus.NEW.value,
    })

    db.flush()
    db.commit()     # <<< CRITICAL FIX: allow worker thread to see the order

    fix_gateway.enqueue_send(order.id)

    return to_schema(order)


@router.get("/orders", response_model=list[OrderSchema])
def list_orders(
    clientId: str | None = Query(default=None),
    symbol: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    repo = OrderRepository(db)
    items = repo.list(clientId, symbol)
    return [to_schema(o) for o in items]


@router.get("/orders/{orderId}", response_model=OrderSchema)
def get_order(orderId: str, db: Session = Depends(get_db)):
    repo = OrderRepository(db)
    order = repo.get(orderId)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return to_schema(order)


@router.post("/orders/{orderId}/cancel", response_model=OrderSchema)
def cancel_order(orderId: str, db: Session = Depends(get_db)):
    """Commit DB before enqueueing FIX cancel event."""
    repo = OrderRepository(db)

    order = repo.get(orderId)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    db.commit()     # <<< CRITICAL FIX: persist order state before FIX cancel

    fix_gateway.enqueue_cancel(order.id)

    return to_schema(order)


@router.get("/positions", response_model=list[PositionSchema])
def positions(clientId: str = Query(...), db: Session = Depends(get_db)):
    repo = PositionsRepository(db)
    items = repo.by_client(clientId)
    return [PositionSchema(**i) for i in items]


# --------------------------
# Mapper DB → API Schema
# --------------------------

def to_schema(o: OrderModel) -> OrderSchema:
    return OrderSchema(
        id=o.id,
        clientId=o.client_id,
        symbol=o.symbol,
        side=o.side,
        type=o.type,
        qty=o.qty,
        price=o.price,
        status=o.status,
        cumQty=o.cum_qty,
        avgPx=o.avg_px,
        createdAt=o.created_at,
        updatedAt=o.updated_at,
    )


from types import SimpleNamespace

from fastapi import APIRouter, Depends, HTTPException, Query, Header
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from .db import get_session
from .models import Order as OrderModel
from .schemas import OrderCreateRequest, Order as OrderSchema, Position as PositionSchema, OrderAmendRequest
from .repositories.orders import OrderRepository
from .repositories.positions import PositionsRepository
# Fase 2 imports
from .repositories.risk_limits import RiskLimitsRepository
from .services.risk_service import validate_order
from .services.metrics import record, snapshot
from .services.reconciliation_service import reconcile_internal
from .utils.enums import OrderStatus, Side, OrderType, TimeInForce
from .services.fix_gateway import fix_gateway
from .services.event_bus import event_bus

router = APIRouter()

get_db = get_session


@router.get("/health")
def health():
    return {"status": "OK"}


@router.post("/orders", response_model=OrderSchema, status_code=201)
async def create_order(payload: OrderCreateRequest, db: AsyncSession = Depends(get_db), x_client_id: str | None = Header(default=None, alias="X-Client-Id")):
    """Create an order after pre-trade risk validation, persist it, commit so FIX worker can see it,
    then enqueue FIX SEND event.

    Contract: Always responds 201 with OrderSchema. If risk rejection occurs, the returned order will have
    status=REJECTED and rejectReason set. The frontend must inspect 'status' to handle rejections.
    """
    # Resolver clientId (body -> header -> fallback)
    resolved_client_id = payload.clientId or x_client_id or "demo-client-1"

    # Fase 2.1 — Validación de riesgo
    risk_repo = RiskLimitsRepository(db)
    client_limit = await risk_repo.by_client_symbol(resolved_client_id, payload.symbol)
    # Si no hay límites definidos para el cliente, definir unos permisivos por defecto para no bloquear MVP
    if client_limit is None:
        # 24x7, sin bloqueo ni límites muy restrictivos
        client_limit = SimpleNamespace(
            client_id=resolved_client_id,
            symbol=None,
            max_notional=1e12,
            max_order_size=1e9,
            trading_hours="00:00-23:59",
            blocked=False,
        )
    # Especificación del símbolo (estático)
    symbol_spec = {
        "ref_price": 2000.0 if payload.symbol.upper().startswith("XAU") else 1.10
    }

    ok, reason = validate_order(payload, client_limit, symbol_spec)
    if not ok:
        # Métricas
        record("orders_rejected", 1)
        record(f"risk_rejects:{reason}", 1)
        # Persist REJECTED order for audit/front/reconciliation
        repo = OrderRepository(db)
        order = await repo.create({
            "client_id": resolved_client_id,
            "symbol": payload.symbol,
            "side": payload.side.value,
            "type": payload.type.value,
            "qty": payload.qty,
            "price": payload.price,
            "time_in_force": payload.timeInForce.value,
            "status": OrderStatus.REJECTED.value,
            "reject_reason": reason,
        })
        await db.commit()
        # WS ORDER_REJECT with full order
        fix_gateway._publish_reject(order, code=reason or "RISK_REJECT", message=reason or "RISK_REJECT")
        # Respond with the rejected order object (align front expectations)
        return to_schema(order)

    # Fase 2.3 — métrica de orden aceptada
    record("orders_total", 1)

    repo = OrderRepository(db)

    order = await repo.create({
        "client_id": resolved_client_id,
        "symbol": payload.symbol,
        "side": payload.side.value,
        "type": payload.type.value,
        "qty": payload.qty,
        "price": payload.price,
        "time_in_force": payload.timeInForce.value,
        "status": OrderStatus.NEW.value,
    })

    await db.commit()     # <<< CRITICAL FIX: allow worker thread to see the order

    await fix_gateway.enqueue_send(order.id)

    return to_schema(order)


@router.get("/orders", response_model=list[OrderSchema])
async def list_orders(
    clientId: str | None = Query(default=None),
    symbol: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    x_client_id: str | None = Header(default=None, alias="X-Client-Id"),
):
    resolved_client_id = clientId or x_client_id or None
    if resolved_client_id is None:
        # Seguridad por defecto: requerir identidad del cliente para listar
        # (puede venir por query ?clientId= o por header X-Client-Id)
        raise HTTPException(status_code=400, detail="clientId is required (query or X-Client-Id header)")
    repo = OrderRepository(db)
    items = await repo.list(resolved_client_id, symbol)
    return [to_schema(o) for o in items]


@router.get("/orders/{orderId}", response_model=OrderSchema)
async def get_order(orderId: str, db: AsyncSession = Depends(get_db)):
    repo = OrderRepository(db)
    order = await repo.get(orderId)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return to_schema(order)


@router.post("/orders/{orderId}/cancel", response_model=OrderSchema)
async def cancel_order(orderId: str, db: AsyncSession = Depends(get_db)):
    """Commit DB before enqueueing FIX cancel event."""
    repo = OrderRepository(db)

    order = await repo.get(orderId)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    await db.commit()     # <<< CRITICAL FIX: persist order state before FIX cancel

    await fix_gateway.enqueue_cancel(order.id)

    return to_schema(order)


@router.patch("/orders/{orderId}", response_model=OrderSchema)
async def amend_order(orderId: str, payload: OrderAmendRequest, db: AsyncSession = Depends(get_db)):
    repo = OrderRepository(db)
    order = await repo.get(orderId)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    editable = {OrderStatus.NEW, OrderStatus.PARTIALLY_FILLED}
    if order.status not in editable:
        raise HTTPException(status_code=400, detail=f"Order not editable in current status ({order.status}). Editable statuses: NEW, PARTIALLY_FILLED. Amend is not allowed in PENDING_SEND or SENT.")

    if payload.qty is None and payload.price is None:
        raise HTTPException(status_code=400, detail="No fields to amend")

    if payload.qty is not None and payload.qty < order.cum_qty:
        raise HTTPException(status_code=400, detail="qty cannot be less than filled quantity")

    # Determine new values
    new_qty = float(payload.qty) if payload.qty is not None else float(order.qty)
    new_price = float(payload.price) if payload.price is not None else (float(order.price) if order.price is not None else None)

    # Re-validate risk
    risk_repo = RiskLimitsRepository(db)
    client_limit = await risk_repo.by_client_symbol(order.client_id, order.symbol)
    if client_limit is None:
        client_limit = SimpleNamespace(
            client_id=order.client_id,
            symbol=None,
            max_notional=1e12,
            max_order_size=1e9,
            trading_hours="00:00-23:59",
            blocked=False,
        )
    symbol_spec = {"ref_price": 2000.0 if order.symbol.upper().startswith("XAU") else 1.10}

    class Tmp:
        def __init__(self, clientId, symbol, side, type, qty, price):
            self.clientId = clientId
            self.symbol = symbol
            self.side = side
            self.type = type
            self.qty = qty
            self.price = price
            self.timeInForce = "GTC"

    tmp = Tmp(order.client_id, order.symbol, order.side, order.type, new_qty, new_price)

    ok, reason = validate_order(tmp, client_limit, symbol_spec)
    if not ok:
        raise HTTPException(status_code=400, detail=reason)

    # Apply changes
    if payload.price is not None:
        order.price = payload.price
    if payload.qty is not None:
        order.qty = payload.qty

    db.add(order)
    await db.commit()

    # Publish update via WS
    fix_gateway._publish_update(order)

    return to_schema(order)


@router.get("/positions", response_model=list[PositionSchema])
async def positions(
    clientId: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    x_client_id: str | None = Header(default=None, alias="X-Client-Id"),
):
    resolved = clientId or x_client_id or "demo-client-1"
    repo = PositionsRepository(db)
    items = await repo.by_client(resolved)
    return [PositionSchema(**i) for i in items]


# Fase 2.3 — Métricas
@router.get("/metrics")
def metrics():
    return snapshot()

# Fase 2.4 — Admin reconcile
@router.get("/admin/reconcile/internal")
async def admin_reconcile(db: AsyncSession = Depends(get_db)):
    return await reconcile_internal(db)


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
        filledQty=o.cum_qty,
        avgPx=o.avg_px,
        rejectReason=getattr(o, "reject_reason", None),
        createdAt=o.created_at,
        updatedAt=o.updated_at,
    )

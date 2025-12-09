from collections import defaultdict
from typing import Dict, List
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from ..models import Order, Execution
from ..repositories.positions import PositionsRepository
from ..utils.enums import OrderStatus

# Fase 2.4 — Reconciliación interna

def reconcile_internal(db: Session) -> dict:
    """
    Verifica:
      - order.cum_qty == sum(executions)
      - status es coherente con qty y cum_qty
      - positions coinciden con executions
    Retorna dict con inconsistencias.
    """
    orders_inconsistent: List[dict] = []

    # Precompute sums of executions per order
    stmt_exec_sums = (
        select(Execution.order_id, func.sum(Execution.exec_qty).label("sum_exec"))
        .group_by(Execution.order_id)
    )
    exec_sums = {row.order_id: float(row.sum_exec or 0.0) for row in db.execute(stmt_exec_sums)}

    # Check orders
    orders = db.execute(select(Order)).scalars().all()
    for o in orders:
        s = float(exec_sums.get(o.id, 0.0))
        inco_reasons: List[str] = []
        if abs((o.cum_qty or 0.0) - s) > 1e-9:
            inco_reasons.append("CUM_QTY_MISMATCH")

        # Coherence with qty and cum_qty
        qty = float(o.qty or 0.0)
        cum = float(o.cum_qty or 0.0)
        st = OrderStatus(o.status)
        if st == OrderStatus.FILLED and abs(cum - qty) > 1e-9:
            inco_reasons.append("STATUS_FILLED_BUT_CUM_QTY_NE_QTY")
        if st == OrderStatus.PARTIALLY_FILLED and (cum <= 0 or cum >= qty):
            inco_reasons.append("STATUS_PARTIAL_INCONSISTENT")
        if st != OrderStatus.FILLED and abs(cum - qty) <= 1e-9 and qty > 0:
            inco_reasons.append("STATUS_NOT_FILLED_BUT_CUM_EQ_QTY")

        if inco_reasons:
            orders_inconsistent.append({
                "orderId": o.id,
                "status": o.status,
                "qty": qty,
                "cumQty": cum,
                "reasons": inco_reasons,
            })

    # Positions vs executions
    positions_inconsistent: List[dict] = []
    # Build positions from executions
    # For each execution, sign depends on order side
    # We need order sides for executions; join executions with orders
    stmt_exec_detail = select(
        Order.client_id, Order.symbol, Order.side, Execution.exec_qty, Execution.exec_px
    ).join(Execution, Execution.order_id == Order.id)
    rows = db.execute(stmt_exec_detail).all()

    agg = defaultdict(float)
    notional = defaultdict(float)
    for r in rows:
        sign = 1.0 if r.side == "BUY" else -1.0
        agg[(r.client_id, r.symbol)] += sign * float(r.exec_qty)
        notional[(r.client_id, r.symbol)] += float(r.exec_qty) * float(r.exec_px)

    # Repo positions
    repo = PositionsRepository(db)
    repo_pos = repo.by_client  # function

    # Compare per client found
    clients = {cid for (cid, _sym) in agg.keys()}
    for cid in clients:
        calc = {(cid, sym): qty for (cid2, sym), qty in agg.items() if cid2 == cid}
        # Convert repo list to mapping
        repolist = repo_pos(cid)
        repo_map = {(p["clientId"], p["symbol"]): float(p["netQty"]) for p in repolist}
        # Compare keys union
        keys = set(calc.keys()) | set(repo_map.keys())
        for key in keys:
            a = float(calc.get(key, 0.0))
            b = float(repo_map.get(key, 0.0))
            if abs(a - b) > 1e-9:
                positions_inconsistent.append({
                    "clientId": key[0],
                    "symbol": key[1],
                    "calcNetQty": a,
                    "repoNetQty": b,
                })

    ok = not orders_inconsistent and not positions_inconsistent
    return {
        "ok": ok,
        "orders_inconsistent": orders_inconsistent,
        "positions_inconsistent": positions_inconsistent,
    }

import asyncio
import random
import logging
from typing import Optional
from ..db import AsyncSessionLocal
from ..models import Order as OrderModel, Execution
from ..utils.enums import OrderStatus
from .events import SendOrderEvent, CancelOrderEvent
# Fase 2.2 — EventBus y métricas
from .event_bus import event_bus
from .metrics import record
from datetime import datetime

# Issue #7: Use proper logging instead of print
logger = logging.getLogger(__name__)


def order_to_payload(order: OrderModel) -> dict:
    return {
        "id": order.id,
        "clientId": order.client_id,
        "symbol": order.symbol,
        "side": order.side,
        "type": order.type,
        "qty": order.qty,
        "price": order.price,
        "timeInForce": order.time_in_force,
        "status": order.status,
        "cumQty": order.cum_qty,
        "filledQty": order.cum_qty,
        "avgPx": order.avg_px,
        "rejectReason": getattr(order, "reject_reason", None),
        "createdAt": order.created_at.isoformat() if isinstance(order.created_at, datetime) else str(order.created_at),
        "updatedAt": order.updated_at.isoformat() if isinstance(order.updated_at, datetime) else str(order.updated_at),
    }


class FixGateway:
    def __init__(self):
        # Issue: Add maxsize to prevent unbounded queue growth under spam
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=10000)
        self.worker_task: Optional[asyncio.Task] = None

    async def start(self):
        """Start the FIX worker task once FastAPI starts."""
        if self.worker_task is None or self.worker_task.done():
            logger.info("Starting FIX worker task...")
            self.worker_task = asyncio.create_task(self._worker())

    async def stop(self):
        """Issue #6: Stop the FIX worker task cleanly on shutdown."""
        if self.worker_task and not self.worker_task.done():
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass
            logger.info("FIX worker task stopped")

    async def enqueue_send(self, order_id: str):
        try:
            self.queue.put_nowait(SendOrderEvent(order_id))
            logger.info(f"[FIX] Enqueued SEND {order_id}")
        except asyncio.QueueFull:
            logger.error(f"[FIX] Queue FULL - rejected SEND for order {order_id}")
            record("fix_queue_full", 1)
            raise RuntimeError("FIX gateway queue is full, order rejected")

    async def enqueue_cancel(self, order_id: str):
        try:
            self.queue.put_nowait(CancelOrderEvent(order_id))
            logger.info(f"[FIX] Enqueued CANCEL {order_id}")
        except asyncio.QueueFull:
            logger.error(f"[FIX] Queue FULL - rejected CANCEL for order {order_id}")
            record("fix_queue_full", 1)
            raise RuntimeError("FIX gateway queue is full, cancel rejected")

    async def _worker(self):
        logger.info("FIX worker STARTED")
        while True:
            evt = await self.queue.get()
            try:
                if isinstance(evt, SendOrderEvent):
                    await self._process_send(evt.order_id)
                elif isinstance(evt, CancelOrderEvent):
                    await self._process_cancel(evt.order_id)
            finally:
                self.queue.task_done()

    async def _process_send(self, order_id: str):
        async with AsyncSessionLocal() as db:
            order = await db.get(OrderModel, order_id)
            if not order:
                logger.warning(f"[FIX] Order NOT FOUND: {order_id}")
                return

            # Issue #4: Check if cancel was requested before starting
            if order.status in (OrderStatus.CANCELED.value, OrderStatus.CANCEL_REQUESTED.value):
                logger.info(f"[FIX] Order {order_id} already canceled/cancel-requested, aborting send")
                return

            # Move to PENDING_SEND
            order.status = OrderStatus.PENDING_SEND.value
            db.add(order)
            await db.commit()
            logger.info(f"[FIX] Order {order_id} → PENDING_SEND")
            self._publish_update(order)

            await asyncio.sleep(0.2)  # simulate delay
            
            # Issue #4: Re-check after sleep (cancel could have happened)
            await db.refresh(order)
            if order.status in (OrderStatus.CANCELED.value, OrderStatus.CANCEL_REQUESTED.value):
                logger.info(f"[FIX] Order {order_id} canceled during PENDING_SEND, aborting")
                return
            
            order.status = OrderStatus.SENT.value
            db.add(order)
            await db.commit()
            logger.info(f"[FIX] Order {order_id} → SENT")
            self._publish_update(order)

            # Process fills
            remaining = order.qty - order.cum_qty
            if remaining <= 0:
                return

            # Issue #4: Check before filling (cancel could have happened)
            await db.refresh(order)
            if order.status in (OrderStatus.CANCELED.value, OrderStatus.CANCEL_REQUESTED.value):
                logger.info(f"[FIX] Order {order_id} canceled before fill, aborting")
                return

            # 10% reject chance
            if random.random() < 0.1:
                order.status = OrderStatus.REJECTED.value
                if not getattr(order, "reject_reason", None):
                    order.reject_reason = "FIX_REJECT"
                db.add(order)
                await db.commit()
                logger.info(f"[FIX] Order {order_id} → REJECTED")
                self._publish_update(order)
                self._publish_reject(order, code=order.reject_reason or "FIX_REJECT", message=order.reject_reason or "FIX_REJECT")
                return

            # Simulate fill or partial fill
            partial = random.random() < 0.5
            lot1 = remaining * (0.4 if partial else 1.0)
            px = order.price or self._mock_market_px(order.symbol)

            # First fill
            exec1 = Execution(order_id=order.id, exec_qty=lot1, exec_px=px)
            db.add(exec1)
            prev_cum = order.cum_qty or 0
            order.cum_qty = prev_cum + lot1
            # Weighted average price: (old_avg*old_qty + px*exec_qty) / (old_qty + exec_qty)
            denom = prev_cum + lot1
            order.avg_px = (0 if denom == 0 else ((order.avg_px or 0) * prev_cum + px * lot1) / denom)
            order.status = (
                OrderStatus.PARTIALLY_FILLED.value
                if order.cum_qty < order.qty
                else OrderStatus.FILLED.value
            )
            db.add(order)
            await db.commit()
            logger.info(f"[FIX] Order {order_id} filled {lot1} @ {px}")
            self._publish_update(order)

            # If partial, finish later
            if order.cum_qty < order.qty:
                await asyncio.sleep(0.3)
                
                # Issue #4: Check before second fill (cancel could have happened)
                await db.refresh(order)
                if order.status in (OrderStatus.CANCELED.value, OrderStatus.CANCEL_REQUESTED.value):
                    logger.info(f"[FIX] Order {order_id} canceled before second fill, aborting")
                    return
                
                lot2 = order.qty - order.cum_qty
                exec2 = Execution(order_id=order.id, exec_qty=lot2, exec_px=px)
                db.add(exec2)
                prev_cum = order.cum_qty or 0
                order.cum_qty = prev_cum + lot2
                # Weighted average price for second fill
                denom = prev_cum + lot2
                order.avg_px = (0 if denom == 0 else ((order.avg_px or 0) * prev_cum + px * lot2) / denom)
                order.status = OrderStatus.FILLED.value
                db.add(order)
                await db.commit()
                logger.info(f"[FIX] Order {order_id} final fill {lot2} @ {px}")
                self._publish_update(order)

    async def _process_cancel(self, order_id: str):
        async with AsyncSessionLocal() as db:
            order = await db.get(OrderModel, order_id)
            if not order:
                logger.warning(f"[FIX] Cancel ignored: Order not found {order_id}")
                return

            # Issue #4: Allow CANCEL_REQUESTED to be processed, treat as cancelable
            if order.status in (
                OrderStatus.FILLED.value,
                OrderStatus.CANCELED.value,
                OrderStatus.REJECTED.value,
            ):
                logger.info(f"[FIX] Cancel ignored: Order {order_id} already terminal")
                return

            await asyncio.sleep(0.2)
            order.status = OrderStatus.CANCELED.value
            db.add(order)
            await db.commit()
            logger.info(f"[FIX] Order {order_id} → CANCELED")
            self._publish_update(order)

    def _mock_market_px(self, symbol: str) -> float:
        base = 2000.0 if symbol.upper().startswith("XAU") else 1.1000
        return round(base + random.uniform(-1, 1), 2)

    def _publish_update(self, order: OrderModel):
        event_bus.publish(
            f"orders.{order.client_id}",
            {
                "type": "ORDER_UPDATE",
                "payload": order_to_payload(order),
            },
        )
        record("fix_events_processed", 1)

    def _publish_reject(self, order: OrderModel, code: str, message: str | None = None):
        event_bus.publish(
            f"orders.{order.client_id}",
            {
                "type": "ORDER_REJECT",
                "payload": {
                    "code": code,
                    "message": message or code,
                    "order": order_to_payload(order),
                },
            },
        )
        record("fix_events_processed", 1)


# Global instance
fix_gateway = FixGateway()

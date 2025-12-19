import asyncio
import logging
import time
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from .services.event_bus import event_bus

# Fase 2.2 — WebSockets de órdenes por cliente

logger = logging.getLogger(__name__)
ws_router = APIRouter()

# Rate-limiting for WS queue full warnings: track last warning time and drop count per client
_ws_drop_state = {}  # {client_id: {"last_warn": timestamp, "drops": count}}


@ws_router.websocket("/ws/orders/{client_id}")
async def ws_orders(websocket: WebSocket, client_id: str):
    # Issue #4: TODO - Add authentication (token/signed clientId in query or session cookie)
    # Currently accepting all connections - DEV ONLY, not production-ready
    await websocket.accept()

    loop = asyncio.get_running_loop()
    # Issue #5: Add maxsize to prevent memory exhaustion under backpressure
    queue: asyncio.Queue = asyncio.Queue(maxsize=1000)

    def on_event(evt):
        # Recibir desde hilos externos de FIX, pasar al loop de asyncio
        # Issue #5: Drop events if queue is full to prevent blocking
        def _put():
            if queue.full():
                # Rate-limit warnings: only log once every 10 seconds per client
                now = time.time()
                if client_id not in _ws_drop_state:
                    _ws_drop_state[client_id] = {"last_warn": 0, "drops": 0}
                
                _ws_drop_state[client_id]["drops"] += 1
                
                if now - _ws_drop_state[client_id]["last_warn"] >= 10.0:
                    drops = _ws_drop_state[client_id]["drops"]
                    logger.warning(
                        f"WS queue full for client {client_id}, dropped {drops} event(s) "
                        f"(last: {evt.get('type', 'unknown')})"
                    )
                    _ws_drop_state[client_id]["last_warn"] = now
                    _ws_drop_state[client_id]["drops"] = 0
                
                return  # Drop event when queue is full
            queue.put_nowait(evt)
        loop.call_soon_threadsafe(_put)

    # Suscribir al tópico del cliente y guardar unsubscribe
    topic = f"orders.{client_id}"
    unsubscribe = event_bus.subscribe(topic, on_event)

    try:
        while True:
            evt = await queue.get()
            await websocket.send_json(evt)
    except WebSocketDisconnect:
        pass
    finally:
        try:
            unsubscribe()
        except Exception:
            pass

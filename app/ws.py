import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from .services.event_bus import event_bus

# Fase 2.2 — WebSockets de órdenes por cliente

ws_router = APIRouter()


@ws_router.websocket("/ws/orders/{client_id}")
async def ws_orders(websocket: WebSocket, client_id: str):
    await websocket.accept()

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def on_event(evt):
        # Recibir desde hilos externos de FIX, pasar al loop de asyncio
        loop.call_soon_threadsafe(queue.put_nowait, evt)

    # Suscribir al tópico del cliente
    topic = f"orders.{client_id}"
    event_bus.subscribe(topic, on_event)

    try:
        while True:
            # Intentar enviar eventos pendientes
            try:
                evt = queue.get_nowait()
            except asyncio.QueueEmpty:
                evt = None
            if evt is not None:
                await websocket.send_json(evt)
            await asyncio.sleep(0.1)
    except WebSocketDisconnect:
        # Conexión terminada por el cliente
        return

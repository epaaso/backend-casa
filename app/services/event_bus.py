from collections import defaultdict
from threading import Lock
from typing import Callable, Any, Dict, List

# Fase 2.2 — Event Bus in-memory (thread-safe básico)

class EventBus:
    def __init__(self):
        self.subscribers: Dict[str, List[Callable[[Any], None]]] = defaultdict(list)
        self._lock = Lock()

    def subscribe(self, topic: str, callback: Callable[[Any], None]) -> None:
        """Suscribe un callback sincrónico que recibirá `event`.
        No devuelve unsubscribe para mantenerlo simple en MVP.
        """
        with self._lock:
            self.subscribers[topic].append(callback)

    def publish(self, topic: str, event: Any) -> None:
        # Copiar lista bajo lock para evitar problemas si cambian durante iteración
        with self._lock:
            callbacks = list(self.subscribers.get(topic, []))
        for cb in callbacks:
            try:
                cb(event)
            except Exception as ex:
                # Evitar que un callback rompa a los demás
                print(f"[EventBus] callback error on {topic}: {ex}")


# Instancia global
event_bus = EventBus()

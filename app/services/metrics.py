from collections import defaultdict
from typing import Dict, Any

# Fase 2.3 — Métricas básicas (in-memory)

_orders_total = 0
_orders_rejected = 0
_risk_rejects: Dict[str, int] = defaultdict(int)
_fix_events_processed = 0


def record(metric_name: str, value: int = 1):
    global _orders_total, _orders_rejected, _fix_events_processed
    if metric_name == "orders_total":
        _orders_total += value
    elif metric_name == "orders_rejected":
        _orders_rejected += value
    elif metric_name.startswith("risk_rejects:"):
        reason = metric_name.split(":", 1)[1]
        _risk_rejects[reason] += value
    elif metric_name == "fix_events_processed":
        _fix_events_processed += value


def snapshot() -> dict[str, Any]:
    return {
        "orders_total": _orders_total,
        "orders_rejected": _orders_rejected,
        "risk_rejects": dict(_risk_rejects),
        "fix_events_processed": _fix_events_processed,
    }

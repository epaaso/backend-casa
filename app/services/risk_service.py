from datetime import datetime, time as time_cls
from typing import Any, Tuple

# Fase 2.1 — Servicio de riesgo (pre-trade)


def _parse_trading_hours(th: str) -> tuple[datetime, datetime] | tuple[time_cls, time_cls]:
    """Parsea string "HH:MM-HH:MM" a tupla de times.
    No gestiona spans de día (e.g., 22:00-02:00) para mantenerlo simple MVP.
    """
    try:
        start_s, end_s = th.split("-")
        sh, sm = [int(x) for x in start_s.split(":")]
        eh, em = [int(x) for x in end_s.split(":")]
        return time_cls(sh, sm), time_cls(eh, em)
    except Exception:
        # si formato inválido, forzar rechazo por seguridad
        return time_cls(23, 59), time_cls(0, 0)


def validate_order(order_request: Any, client_risk: Any, symbol_spec: dict) -> Tuple[bool, str | None]:
    """
    Valida un request de orden contra límites de riesgo y especificación del símbolo.
    Reglas:
      - qty > 0
      - si type == LIMIT → price requerido
      - si type == MARKET → price debe ser None
      - notional = qty * price (si MARKET usar precio de referencia del symbol_spec)
      - notional <= max_notional
      - qty <= max_order_size
      - hora actual ∈ trading_hours (string tipo "09:00-16:00")
      - símbolo no bloqueado
    Retorna (ok, reason) donde reason es un string con la causa del rechazo.
    """
    # qty > 0
    qty = float(order_request.qty)
    if qty <= 0:
        return False, "INVALID_QTY"

    otype = getattr(order_request, "type")
    price = getattr(order_request, "price", None)

    # coherencia de precio según tipo
    if str(otype) in ("OrderType.LIMIT", "LIMIT"):
        if price is None:
            return False, "PRICE_REQUIRED"
    if str(otype) in ("OrderType.MARKET", "MARKET"):
        if price is not None:
            return False, "PRICE_NOT_ALLOWED"

    # símbolo bloqueado
    if getattr(client_risk, "blocked", False):
        return False, "SYMBOL_BLOCKED"

    # horario de trading
    th = getattr(client_risk, "trading_hours", "00:00-23:59")
    start_t, end_t = _parse_trading_hours(th)
    now_t = datetime.now().time()
    if not (start_t <= now_t <= end_t):
        return False, "OUTSIDE_TRADING_HOURS"

    # notional
    if price is None:
        ref_px = symbol_spec.get("ref_price")
        try:
            price = float(ref_px)
        except Exception:
            return False, "MISSING_REFERENCE_PRICE"
    notional = qty * float(price)
    max_notional = float(getattr(client_risk, "max_notional", float("inf")))
    if notional > max_notional:
        return False, "NOTIONAL_LIMIT_EXCEEDED"

    # tamaño máximo por orden
    max_order_size = float(getattr(client_risk, "max_order_size", float("inf")))
    if qty > max_order_size:
        return False, "ORDER_SIZE_LIMIT_EXCEEDED"

    return True, None

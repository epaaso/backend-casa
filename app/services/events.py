from dataclasses import dataclass

@dataclass
class SendOrderEvent:
    order_id: str

@dataclass
class CancelOrderEvent:
    order_id: str

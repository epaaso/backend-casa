from datetime import datetime
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from .utils.enums import Side, OrderType, TimeInForce, OrderStatus

class OrderCreateRequest(BaseModel):
    clientId: Optional[str] = None
    symbol: str
    side: Side
    type: OrderType
    qty: float = Field(gt=0)
    price: Optional[float] = None
    timeInForce: TimeInForce = TimeInForce.GTC

    @field_validator("price")
    @classmethod
    def validate_price(cls, v, info):
        values = info.data
        otype = values.get("type")
        if otype == OrderType.LIMIT and v is None:
            raise ValueError("price is required for LIMIT orders")
        if otype == OrderType.MARKET and v is not None:
            raise ValueError("price must be null for MARKET orders")
        return v

class Order(BaseModel):
    id: str
    clientId: str
    symbol: str
    side: Side
    type: OrderType
    qty: float
    price: Optional[float] = None
    timeInForce: TimeInForce
    status: OrderStatus
    cumQty: float
    filledQty: float
    avgPx: Optional[float] = None
    rejectReason: Optional[str] = None
    createdAt: datetime
    updatedAt: datetime

    class Config:
        from_attributes = True

class OrderAmendRequest(BaseModel):
    price: Optional[float] = None
    qty: Optional[float] = None

class Position(BaseModel):
    clientId: str
    symbol: str
    netQty: float
    avgPx: float
    unrealizedPnl: float

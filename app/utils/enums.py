from enum import Enum

class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"

class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"

class TimeInForce(str, Enum):
    GTC = "GTC"
    DAY = "DAY"
    IOC = "IOC"
    FOK = "FOK"

class OrderStatus(str, Enum):
    NEW = "NEW"
    PENDING_SEND = "PENDING_SEND"
    SENT = "SENT"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    CANCELED = "CANCELED"

class DepositStatus(str, Enum):
    """Estados posibles para la intención de depósito."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"

class WithdrawalStatus(str, Enum):
    """Estados del ciclo de vida de una solicitud de retiro."""
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    PROCESSING = "processing"
    COMPLETED = "completed"
    CANCELED = "canceled"


class KYCStatus(str, Enum):
    """Estado del proceso KYC."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"

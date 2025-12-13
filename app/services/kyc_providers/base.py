from abc import ABC, abstractmethod
from typing import Dict, Any


class KYCProvider(ABC):
    @abstractmethod
    async def create_applicant(self, *, client_id: str, user_data: dict) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def get_access_token(self, applicant_id: str) -> str:
        pass

    @abstractmethod
    async def get_applicant_status(self, applicant_id: str) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def process_webhook(self, payload: dict) -> Dict[str, Any]:
        """Return normalized: { session_id, status, reason?, provider_data?, verification_level?, document_types? }"""
        pass

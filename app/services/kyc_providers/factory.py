import os
from .mock import MockKYCProvider
from .sumsub import SumsubKYCProvider


def get_kyc_provider(name: str):
    name = (name or "sumsub").lower()
    debug = os.getenv("DEBUG", "0") == "1" or os.getenv("TESTING", "0") == "1"
    if name in ("mock", "mock_sumsub") or debug:
        return MockKYCProvider()
    if name == "sumsub":
        return SumsubKYCProvider()
    # fallback
    return MockKYCProvider()

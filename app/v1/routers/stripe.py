import os
import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, Header
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from ...db import get_session
from ...utils.enums import DepositStatus
from ...models import DepositIntent
from ..repositories.deposits import DepositIntentRepository

router = APIRouter(prefix="/stripe", tags=["Stripe Payments"])

stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")


def _is_sandbox() -> bool:
    return os.getenv("DEBUG", "0") == "1" or os.getenv("TESTING", "0") == "1"


class CreateCheckoutRequest(BaseModel):
    deposit_id: str


class CreateCheckoutResponse(BaseModel):
    checkout_url: str
    session_id: str


@router.post("/create-checkout-session", response_model=CreateCheckoutResponse)
async def create_checkout_session(
    req: CreateCheckoutRequest,
    client_id_header: str | None = Header(default=None, alias="X-Client-Id"),
    db: AsyncSession = Depends(get_session),
):
    client_id = client_id_header or "demo-client-1"
    repo = DepositIntentRepository(db)

    deposit = await repo.get_by_id(req.deposit_id, client_id)
    if not deposit:
        raise HTTPException(status_code=404, detail="Deposit not found")

    if deposit.status != DepositStatus.PENDING.value:
        raise HTTPException(status_code=400, detail=f"Deposit is already {deposit.status}")

    if deposit.amount <= 0:
        raise HTTPException(status_code=400, detail=f"Invalid deposit amount: {deposit.amount}")

    try:
        unit_amount = int(float(deposit.amount) * 100)

        # Issue #3: Wrap blocking Stripe call in threadpool
        def _create_session():
            return stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[{
                    "price_data": {
                        "currency": (deposit.currency or "USD").lower(),
                        "product_data": {
                            "name": "Depósito a cuenta de trading",
                            "description": f"Depósito de {deposit.amount} {deposit.currency}",
                        },
                        "unit_amount": unit_amount,
                    },
                    "quantity": 1,
                }],
                mode="payment",
                metadata={
                    "deposit_id": str(deposit.id),
                    "client_id": str(client_id),
                },
                success_url=f"{FRONTEND_URL}/deposit/success?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{FRONTEND_URL}/deposit/cancel",
            )
        
        session = await run_in_threadpool(_create_session)

        deposit.provider = "stripe"
        deposit.provider_reference = session.id
        deposit.payment_url = session.url
        deposit.status = DepositStatus.PROCESSING.value
        await db.commit()
        await db.refresh(deposit)

        return CreateCheckoutResponse(checkout_url=session.url, session_id=session.id)

    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=f"Stripe error: {str(e)}")


@router.post("/simulate-payment-success/{deposit_id}")
async def simulate_payment_success(
    deposit_id: str,
    client_id_header: str | None = Header(default=None, alias="X-Client-Id"),
    db: AsyncSession = Depends(get_session),
):
    if not _is_sandbox():
        raise HTTPException(status_code=403, detail="Este endpoint solo está disponible en modo desarrollo")

    client_id = client_id_header or "demo-client-1"
    repo = DepositIntentRepository(db)

    deposit = await repo.get_by_id(deposit_id, client_id)
    if not deposit:
        raise HTTPException(status_code=404, detail="Depósito no encontrado")

    if deposit.status == DepositStatus.COMPLETED.value:
        return {"status": "already_completed", "deposit_id": deposit.id}

    deposit.status = DepositStatus.COMPLETED.value
    deposit.confirmed_amount = float(deposit.amount)
    await db.commit()
    await db.refresh(deposit)

    return {
        "status": "success",
        "deposit_id": deposit.id,
        "amount": deposit.amount,
        "confirmed_amount": deposit.confirmed_amount,
        "currency": deposit.currency,
    }


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="Stripe-Signature"),
    db: AsyncSession = Depends(get_session),
):
    payload = await request.body()

    try:
        event = stripe.Webhook.construct_event(payload, stripe_signature, WEBHOOK_SECRET)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    repo = DepositIntentRepository(db)

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        deposit_id = session.get("metadata", {}).get("deposit_id")
        if not deposit_id:
            return {"status": "ignored", "reason": "missing_deposit_id"}

        deposit = await repo.get_by_id_no_owner(deposit_id)
        if not deposit:
            return {"status": "error", "message": "Deposit not found"}

        deposit.status = DepositStatus.COMPLETED.value
        amount_total = session.get("amount_total")
        if amount_total is not None:
            deposit.confirmed_amount = float(amount_total) / 100.0
        await db.commit()
        return {"status": "success"}

    if event["type"] == "checkout.session.expired":
        session = event["data"]["object"]
        deposit_id = session.get("metadata", {}).get("deposit_id")
        if deposit_id:
            deposit = await repo.get_by_id_no_owner(deposit_id)
            if deposit:
                deposit.status = DepositStatus.CANCELED.value
                await db.commit()
        return {"status": "success"}

    if event["type"] == "payment_intent.payment_failed":
        # Not enough info by default; ignoring.
        return {"status": "ignored"}

    return {"status": "ignored"}


@router.get("/session/{session_id}")
async def get_stripe_session(session_id: str):
    try:
        # Issue #3: Wrap blocking Stripe call in threadpool
        def _retrieve():
            return stripe.checkout.Session.retrieve(session_id)
        
        s = await run_in_threadpool(_retrieve)
        return {
            "session_id": s.id,
            "payment_status": s.payment_status,
            "amount_total": s.amount_total,
            "currency": s.currency,
        }
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=f"Stripe error: {str(e)}")

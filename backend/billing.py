import os

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from starlette.concurrency import run_in_threadpool

from .auth import ORIGIN, limit, user
from .db import MODE, engine

router = APIRouter(tags=["billing"])
DEFAULTS = {"free": "40", "standard": "150", "premium": "500"}


def allowance(plan, action):
    return int(os.getenv(f"{plan.upper()}_{action.upper()}_DAILY", DEFAULTS[plan]))


def prices():
    return {plan: os.getenv("STRIPE_" + plan.upper() + "_PRICE_ID", "") for plan in ("standard", "premium")}


def enabled():
    key = os.getenv("STRIPE_SECRET_KEY", "")
    return MODE == "live" and key.startswith(("sk_test_", "rk_test_")) and bool(os.getenv("STRIPE_WEBHOOK_SECRET")) \
        and all(prices().values()) and len(set(prices().values())) == 2


def stripe_sdk():
    if not enabled():
        raise HTTPException(503, "Stripe test billing is unavailable")
    import stripe
    stripe.api_key = os.environ["STRIPE_SECRET_KEY"]
    stripe.default_http_client = stripe.RequestsClient(timeout=10)
    return stripe


@router.get("/subscriptions")
def plans():
    return {"enabled": enabled(), "plans": [
        {"id": plan, "search": allowance(plan, "search"), "chat": allowance(plan, "chat")} for plan in DEFAULTS
    ]}


class Checkout(BaseModel):
    plan: str = Field(pattern="^(standard|premium)$")


@router.post("/billing/checkout")
def checkout(body: Checkout, account=Depends(user)):
    stripe = stripe_sdk()
    if not account["verified"]:
        raise HTTPException(403, "Verify your email before checking out")
    if account["subscription_status"] not in {"none", "canceled", "incomplete_expired"}:
        raise HTTPException(409, "Use the billing portal to manage the current subscription")
    uid = account["id"]
    limit("checkout:" + uid, 10, 3600)
    customer = account["customer"]
    try:
        if not customer:
            customer = stripe.Customer.create(email=account["email"], metadata={"account_id": uid},
                                              idempotency_key="culinary-customer-" + uid).id
            with engine.begin() as db:
                db.execute(text("UPDATE accounts SET customer=:customer WHERE id=:id"),
                           {"id": uid, "customer": customer})
        with engine.begin() as db:
            if engine.dialect.name == "postgresql":
                db.execute(text("SELECT id FROM accounts WHERE id=:id FOR UPDATE"), {"id": uid})
            else:
                db.execute(text("UPDATE accounts SET id=id WHERE id=:id"), {"id": uid})
            subscriptions = stripe.Subscription.list(customer=customer, status="all", limit=100)
            if any(item.status not in {"canceled", "incomplete_expired"} for item in subscriptions.auto_paging_iter()):
                raise HTTPException(409, "Use the billing portal to manage the current subscription")
            for session in stripe.checkout.Session.list(customer=customer, status="open", limit=20).data:
                if session.metadata.get("plan") == body.plan and session.url:
                    return {"url": session.url}
                stripe.checkout.Session.expire(session.id)
            session = stripe.checkout.Session.create(
                customer=customer, mode="subscription", line_items=[{"price": prices()[body.plan], "quantity": 1}],
                success_url=ORIGIN + "/?billing=success", cancel_url=ORIGIN + "/?billing=canceled", metadata={"plan": body.plan},
            )
    except stripe.StripeError:
        raise HTTPException(502, "Stripe Checkout is temporarily unavailable")
    return {"url": session.url}


@router.post("/billing/portal")
def portal(account=Depends(user)):
    stripe = stripe_sdk()
    if not account["customer"]:
        raise HTTPException(409, "No billing account exists")
    try:
        return {"url": stripe.billing_portal.Session.create(customer=account["customer"], return_url=ORIGIN).url}
    except stripe.StripeError:
        raise HTTPException(502, "The billing portal is temporarily unavailable")


def apply_event(stripe, data, signature):
    try:
        event = stripe.Webhook.construct_event(data, signature, os.environ["STRIPE_WEBHOOK_SECRET"])
    except (ValueError, stripe.SignatureVerificationError):
        raise HTTPException(400, "Invalid webhook signature")
    if event["livemode"]:
        raise HTTPException(400, "Expected a test-mode event")
    event_type = event["type"]
    if not event_type.startswith("customer.subscription.") and event_type not in {"invoice.payment_failed", "invoice.paid"}:
        return {"received": True}
    customer = event["data"]["object"].get("customer")
    if not customer:
        return {"received": True}
    with engine.begin() as db:
        inserted = db.execute(text("INSERT INTO webhook_events VALUES (:id) ON CONFLICT(id) DO NOTHING"), {"id": event["id"]})
        if not inserted.rowcount:
            return {"received": True}
        locked = db.execute(text("UPDATE accounts SET customer=customer WHERE customer=:customer"), {"customer": customer})
        if not locked.rowcount:
            return {"received": True}
        try:
            subscriptions = stripe.Subscription.list(customer=customer, status="all", limit=100)
            status, plan = "none", "free"
            ranking = {"none": 0, "canceled": 1, "incomplete_expired": 1}
            for subscription in subscriptions.auto_paging_iter():
                current_status = subscription["status"]
                if ranking.get(current_status, 2) > ranking.get(status, 2):
                    status = current_status
                if current_status not in {"active", "trialing"} or subscription.get("pause_collection"):
                    continue
                ids = {item["price"]["id"] for item in subscription["items"]["data"]}
                for candidate in ("premium", "standard"):
                    if prices()[candidate] in ids and (plan == "free" or candidate == "premium"):
                        plan, status = candidate, current_status
        except stripe.StripeError:
            raise HTTPException(503, "Could not reconcile subscription")
        db.execute(text("UPDATE accounts SET plan=:plan,subscription_status=:status WHERE customer=:customer"),
                   {"plan": plan, "status": status, "customer": customer})
    return {"received": True}


@router.post("/billing/webhook")
async def webhook(request: Request):
    stripe = stripe_sdk()
    chunks = bytearray()
    async for chunk in request.stream():
        chunks.extend(chunk)
        if len(chunks) > 1024 * 1024:
            raise HTTPException(413, "Webhook body is too large")
    return await run_in_threadpool(apply_event, stripe, bytes(chunks), request.headers.get("stripe-signature", ""))

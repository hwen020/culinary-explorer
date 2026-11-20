import hashlib
import os
import secrets
import smtplib
import time
from email.message import EmailMessage
from urllib.parse import urlencode
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from .db import DEPLOYMENT, MODE, engine

router = APIRouter(prefix="/auth", tags=["authentication"])
COOKIE = "culinary_preview" if DEPLOYMENT == "preview" else "culinary_" + MODE
ORIGIN = (os.getenv("RENDER_EXTERNAL_URL") if DEPLOYMENT == "preview" else None) or os.getenv("APP_ORIGIN", "http://localhost:5173")
ORIGIN = ORIGIN.rstrip("/")
SECURE = ORIGIN.startswith("https://")


class Email(BaseModel):
    email: str = Field(min_length=3, max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

    @field_validator("email", mode="before")
    @classmethod
    def normalize(cls, value):
        return value.strip().lower() if isinstance(value, str) else value


class Credentials(Email):
    password: str = Field(min_length=10, max_length=256)


class Token(BaseModel):
    token: str = Field(min_length=32, max_length=200)


class Reset(Token):
    password: str = Field(min_length=10, max_length=256)


def now():
    return int(time.time())


def key(value):
    return hashlib.sha256(value.encode()).hexdigest()


def password_hash(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 260000).hex()


def limit(scope, maximum, window):
    period = now() // window * window
    with engine.begin() as db:
        count = db.execute(text("""
            INSERT INTO counters VALUES (:scope,:period,1)
            ON CONFLICT (scope,period) DO UPDATE SET count=counters.count+1
            RETURNING count
        """), {"scope": scope, "period": period}).scalar_one()
    if count > maximum:
        raise HTTPException(429, "Usage limit reached", headers={"Retry-After": str(period + window - now())})


def optional_user(request: Request):
    token = request.cookies.get(COOKIE)
    if not token:
        return None
    with engine.connect() as db:
        return db.execute(text("""
            SELECT a.* FROM accounts a JOIN sessions s ON a.id=s.user_id
            WHERE s.token=:token AND s.expires>:now
        """), {"token": key(token), "now": now()}).mappings().first()


def user(account=Depends(optional_user)):
    if account is None:
        raise HTTPException(401, "Sign in to continue")
    return account


def admin(account=Depends(user)):
    if DEPLOYMENT == "preview":
        raise HTTPException(404, "Unavailable in public preview")
    variable = "PRODUCTION_ADMIN_EMAILS" if DEPLOYMENT == "production" else "ADMIN_EMAILS"
    addresses = {value.strip().lower() for value in os.getenv(variable, "").split(",") if value.strip()}
    if not account["verified"] or account["email"] not in addresses:
        raise HTTPException(403, "Administrator access required")
    return account


def public_account(account):
    return {field: account[field] for field in ("id", "email", "verified", "plan", "subscription_status")}


def send_action(account, purpose):
    token = secrets.token_urlsafe(32)
    with engine.begin() as db:
        db.execute(text("INSERT INTO action_tokens VALUES (:token,:uid,:purpose,:expires)"),
                   {"token": key(token), "uid": account["id"], "purpose": purpose, "expires": now() + 3600})
    if MODE == "demo":
        return None
    host = os.getenv("SMTP_HOST")
    if not host:
        return None
    message = EmailMessage()
    message["From"] = os.environ["SMTP_FROM"]
    message["To"] = account["email"]
    message["Subject"] = "Culinary Explorer account link"
    message.set_content(ORIGIN + "/?" + urlencode({"action": purpose, "token": token}))
    try:
        with smtplib.SMTP(host, int(os.getenv("SMTP_PORT", "587")), timeout=10) as smtp:
            smtp.starttls()
            if os.getenv("SMTP_USERNAME"):
                smtp.login(os.environ["SMTP_USERNAME"], os.environ["SMTP_PASSWORD"])
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException):
        raise HTTPException(503, "Email delivery unavailable")


@router.post("/register", status_code=201)
def register(body: Credentials, request: Request):
    limit("register:" + request.client.host, 12, 3600)
    account = {"id": str(uuid4()), "email": body.email, "salt": secrets.token_hex(16), "verified": int(MODE == "demo")}
    account["hash"] = password_hash(body.password, account["salt"])
    try:
        with engine.begin() as db:
            db.execute(text("""
                INSERT INTO accounts (id,email,salt,password_hash,verified)
                VALUES (:id,:email,:salt,:hash,:verified)
            """), account)
    except IntegrityError:
        raise HTTPException(409, "Account already exists")
    if MODE == "live":
        try:
            send_action(account, "verify")
        except HTTPException:
            return {"verification_required": True, "delivery_pending": True}
    return {"verification_required": MODE == "live"}


@router.post("/login")
def login(body: Credentials, request: Request, response: Response):
    limit("login:" + request.client.host, 30, 900)
    limit("login-email:" + key(body.email), 10, 900)
    with engine.connect() as db:
        account = db.execute(text("SELECT * FROM accounts WHERE email=:email"), {"email": body.email}).mappings().first()
    digest = password_hash(body.password, account["salt"] if account else "00" * 16)
    if not account or not secrets.compare_digest(digest, account["password_hash"]):
        raise HTTPException(401, "Incorrect credentials")
    token = secrets.token_urlsafe(32)
    lifetime = 604800
    with engine.begin() as db:
        previous = request.cookies.get(COOKIE)
        if previous:
            db.execute(text("DELETE FROM sessions WHERE token=:token"), {"token": key(previous)})
        db.execute(text("INSERT INTO sessions VALUES (:token,:uid,:expires)"),
                   {"token": key(token), "uid": account["id"], "expires": now() + lifetime})
    response.set_cookie(COOKIE, token, max_age=lifetime, httponly=True, secure=SECURE, samesite="lax")
    return public_account(account)


@router.post("/logout")
def logout(request: Request, response: Response):
    token = request.cookies.get(COOKIE)
    if token:
        with engine.begin() as db:
            db.execute(text("DELETE FROM sessions WHERE token=:token"), {"token": key(token)})
    response.delete_cookie(COOKIE, httponly=True, secure=SECURE, samesite="lax")
    return {"ok": True}


@router.post("/verification/request")
def verification_request(account=Depends(user)):
    limit("verify:" + account["id"], 4, 3600)
    if not account["verified"]:
        send_action(account, "verify")
    return {"accepted": True}


@router.post("/password/request")
def password_request(body: Email, request: Request):
    limit("reset:" + request.client.host, 8, 3600)
    with engine.connect() as db:
        account = db.execute(text("SELECT id,email FROM accounts WHERE email=:email"), {"email": body.email}).mappings().first()
    if account:
        try:
            send_action(account, "reset")
        except HTTPException:
            pass
    return {"accepted": True}


def consume(db, token, purpose):
    uid = db.execute(text("""
        DELETE FROM action_tokens WHERE token=:token AND purpose=:purpose AND expires>:now RETURNING user_id
    """), {"token": key(token), "purpose": purpose, "now": now()}).scalar()
    if not uid:
        raise HTTPException(400, "Invalid or expired link")
    return uid


@router.post("/verification/confirm")
def verify(body: Token):
    with engine.begin() as db:
        uid = consume(db, body.token, "verify")
        db.execute(text("UPDATE accounts SET verified=1 WHERE id=:uid"), {"uid": uid})
    return {"ok": True}


@router.post("/password/confirm")
def reset(body: Reset):
    salt = secrets.token_hex(16)
    digest = password_hash(body.password, salt)
    with engine.begin() as db:
        uid = consume(db, body.token, "reset")
        db.execute(text("UPDATE accounts SET salt=:salt,password_hash=:digest WHERE id=:uid"),
                   {"uid": uid, "salt": salt, "digest": digest})
        db.execute(text("DELETE FROM sessions WHERE user_id=:uid"), {"uid": uid})
        db.execute(text("DELETE FROM action_tokens WHERE user_id=:uid AND purpose='reset'"), {"uid": uid})
    return {"ok": True}

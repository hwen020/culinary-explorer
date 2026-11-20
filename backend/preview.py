"""Restricted, same-origin public demo entry point."""
import os
import re
import secrets
import time
from collections import deque
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

from fastapi import HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import text
from starlette.staticfiles import StaticFiles

if os.getenv("CULINARY_DEPLOYMENT") != "preview":
    raise RuntimeError("Public preview must be explicitly selected")

from . import auth
from .db import engine
from .main import app as api

origin = urlsplit(auth.ORIGIN)
if (not origin.hostname or origin.username is not None or origin.path or origin.query or origin.fragment
        or (origin.scheme != "https" and not (
            origin.scheme == "http" and origin.hostname in {"localhost", "127.0.0.1"}
            and not os.getenv("RENDER")))):
    raise RuntimeError("Public preview requires HTTPS outside localhost")

DIST = Path(os.getenv("CULINARY_DIST_DIR", "dist")).resolve()
if not (DIST / "index.html").is_file():
    raise RuntimeError("Build the React frontend before starting the preview")

READ = re.compile(r"/api/(?:health|locations|users/me|favorites|conversations(?:/[0-9a-f-]{36})?|restaurants/demo-[0-9]+)")
WRITE = {
    ("POST", "/api/preview/guest"), ("POST", "/api/preview/leave"),
    ("POST", "/api/search"), ("POST", "/api/chat"), ("POST", "/api/restaurants/export"),
    ("POST", "/api/users/me/demo-reset"),
}


def allowed(method, path):
    if method == "GET":
        return bool(READ.fullmatch(path))
    if (method, path) in WRITE:
        return True
    if method in {"PUT", "DELETE"} and re.fullmatch(r"/api/favorites/demo-[0-9]+", path):
        return True
    return method == "DELETE" and bool(re.fullmatch(r"/api/conversations/[0-9a-f-]{36}", path))


@api.post("/api/preview/guest", status_code=201)
def guest(request: Request, response: Response):
    if auth.optional_user(request):
        return {"guest": True}
    auth.limit("preview:guest", 90, 3600)
    uid = str(uuid4())
    token = secrets.token_urlsafe(32)
    lifetime = 7200
    with engine.begin() as db:
        db.execute(text("BEGIN IMMEDIATE"))
        db.execute(text("DELETE FROM counters WHERE period < :cutoff"), {"cutoff": auth.now() - 172800})
        db.execute(text("DELETE FROM accounts WHERE id NOT IN (SELECT user_id FROM sessions WHERE expires > :now)"), {"now": auth.now()})
        if db.execute(text("SELECT COUNT(*) FROM accounts")).scalar_one() >= 120:
            raise HTTPException(503, "Guest capacity reached. Try again later.")
        db.execute(text("INSERT INTO accounts (id,email,salt,password_hash,verified) VALUES (:id,:email,'','',1)"),
                   {"id": uid, "email": uid + "@example.test"})
        db.execute(text("INSERT INTO sessions VALUES (:token,:id,:expires)"),
                   {"token": auth.key(token), "id": uid, "expires": auth.now() + lifetime})
    response.set_cookie(auth.COOKIE, token, max_age=lifetime, secure=auth.SECURE, httponly=True, samesite="lax")
    return {"guest": True}


@api.post("/api/preview/leave")
def leave(request: Request, response: Response):
    account = auth.optional_user(request)
    if account:
        with engine.begin() as db:
            db.execute(text("DELETE FROM accounts WHERE id=:id"), {"id": account["id"]})
    response.delete_cookie(auth.COOKIE, secure=auth.SECURE, httponly=True, samesite="lax")
    return {"ok": True}


api.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")


@api.get("/{path:path}", include_in_schema=False)
def show_spa(path: str):
    return FileResponse(DIST / "index.html", headers={"Cache-Control": "no-cache"})


recent = deque()


async def app(scope, receive, send):
    if scope["type"] != "http":
        await api(scope, receive, send)
        return
    path, method = scope["path"], scope["method"]
    headers = dict(scope["headers"])

    async def reject(status, detail):
        await JSONResponse({"detail": detail}, status_code=status,
                           headers={"Cache-Control": "no-store"})(scope, receive, send)

    if path == "/api" or path.startswith("/api/"):
        if not allowed(method, path):
            await reject(404, "Unavailable in public preview")
            return
        if path != "/api/health":
            now = time.monotonic()
            while recent and recent[0] <= now - 60:
                recent.popleft()
            if len(recent) >= 240:
                await reject(429, "Preview capacity reached. Try again shortly.")
                return
            recent.append(now)
        if method != "GET":
            if headers.get(b"origin") != auth.ORIGIN.encode("ascii"):
                await reject(403, "Origin not allowed")
                return
            payload = bytearray()
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                chunk = message.get("body", b"")
                if len(payload) + len(chunk) > 4096:
                    await reject(413, "Preview requests are limited to 4 KiB")
                    return
                payload.extend(chunk)
                if not message.get("more_body"):
                    break
            upstream_receive = receive
            async def replay():
                nonlocal payload
                if payload is None:
                    return await upstream_receive()
                body, payload = bytes(payload), None
                return {"type": "http.request", "body": body, "more_body": False}
            receive = replay
    elif path in {"/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"}:
        await reject(404, "Unavailable in public preview")
        return

    async def security_headers(message):
        if message["type"] == "http.response.start":
            message["headers"] = [*message["headers"],
                (b"content-security-policy", b"default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"),
                (b"referrer-policy", b"no-referrer"),
                (b"permissions-policy", b"geolocation=(), camera=(), microphone=()")]
        await send(message)

    await api(scope, receive, security_headers)

import csv
import json
import os
import time
from contextlib import asynccontextmanager
from typing import Optional
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import Field
from sqlalchemy import text

from . import auth, billing, places, rag, worker
from .db import DEPLOYMENT, MODE, engine, migrate


@asynccontextmanager
async def lifespan(_):
    migrate()
    places.seed()
    try:
        yield
    finally:
        engine.dispose()


app = FastAPI(title="Culinary Explorer", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[auth.ORIGIN], allow_credentials=True,
                   allow_methods=["GET", "POST", "PUT", "DELETE"], allow_headers=["Content-Type"])
if DEPLOYMENT != "preview":
    app.include_router(auth.router, prefix="/api")
    app.include_router(billing.router, prefix="/api")


@app.middleware("http")
async def protect_origin(request, call_next):
    origin = request.headers.get("origin")
    if request.method in {"POST", "PUT", "DELETE", "PATCH"} and origin and origin != auth.ORIGIN:
        return JSONResponse({"detail": "Origin not allowed"}, status_code=403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    if request.url.path.startswith("/api"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/api/health")
def health():
    with engine.connect() as db:
        db.execute(text("SELECT 1"))
    return {"status": "ok", "mode": MODE, "preview": DEPLOYMENT == "preview", "providers": rag.providers(),
            "maps_key": os.getenv("GOOGLE_BROWSER_KEY", "") if MODE == "live" else ""}


@app.get("/api/users/me")
def profile(account=Depends(auth.user)):
    with engine.connect() as db:
        searches = db.execute(text("SELECT label,created FROM searches WHERE user_id=:uid ORDER BY created DESC LIMIT 30"),
                              {"uid": account["id"]}).mappings().all()
    return {**auth.public_account(account), "searches": searches}


@app.get("/api/locations")
def location(request: Request, q: str = ""):
    auth.limit("location:" + request.client.host, 30, 60)
    if len(q) > 250:
        raise HTTPException(422, "Location is too long")
    return places.resolve(q)


def quota(request, account, action):
    plan = account["plan"] if account else "free"
    uid = account["id"] if account else request.client.host
    auth.limit(action + ":" + uid, 40 if DEPLOYMENT == "preview" else billing.allowance(plan, action), 86400)


@app.post("/api/search")
def search(body: places.Search, request: Request, account=Depends(auth.optional_user)):
    quota(request, account, "search")
    center, records = places.search(body)
    if account:
        with engine.begin() as db:
            db.execute(text("INSERT INTO searches VALUES (:id,:uid,:label,:created)"),
                       {"id": str(uuid4()), "uid": account["id"], "label": body.location or "Selected coordinates", "created": auth.now()})
    start = (body.page - 1) * 20
    return {"center": center, "items": records[start:start+20], "total": len(records), "page": body.page}


@app.post("/api/restaurants/export")
def export(body: places.Search):
    if MODE == "live" and body.dataset == "google":
        raise HTTPException(403, "Google Places content is unavailable for CSV export")
    _, rows = places.search(body)
    if any(row.source == "google" for row in rows):
        raise HTTPException(403, "Google Places content is unavailable for CSV export")
    return Response(places.csv_export(rows), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="restaurants.csv"'})


@app.get("/api/restaurants/{place_id}")
def details(place_id: str, request: Request):
    from urllib.parse import quote

    with engine.connect() as db:
        row = db.execute(text("SELECT * FROM restaurants WHERE id=:id"), {"id": place_id}).mappings().first()
    if not row:
        raise HTTPException(404, "Restaurant not found")
    if row["source"] != "google":
        return places.decode(row)
    auth.limit("details:" + request.client.host, 30, 60)
    raw = places.request_google("https://places.googleapis.com/v1/places/" + quote(place_id, safe=""), method="GET",
                                headers={"X-Goog-Api-Key": os.getenv("GOOGLE_MAPS_API_KEY", ""),
                                         "X-Goog-FieldMask": ",".join(places.FIELDS)})
    return places.GooglePlace.model_validate(raw).normalize()


class Favorite(places.BaseModel):
    collection: str = Field(default="Favorites", min_length=1, max_length=80)


@app.get("/api/favorites")
def favorites(account=Depends(auth.user)):
    with engine.connect() as db:
        rows = db.execute(text("""
            SELECT f.collection,r.* FROM favorites f JOIN restaurants r ON r.id=f.place_id
            WHERE f.user_id=:uid ORDER BY f.collection,r.id LIMIT 500
        """), {"uid": account["id"]}).mappings().all()
    return [{"id": row["id"], "collection": row["collection"],
             "restaurant": places.decode(row) if row["source"] != "google" else None} for row in rows]


@app.put("/api/favorites/{place_id}")
def save_favorite(place_id: str, favorite: Favorite, account=Depends(auth.user)):
    with engine.begin() as db:
        values = {"uid": account["id"], "id": place_id, "collection": favorite.collection}
        if not db.execute(text("SELECT id FROM restaurants WHERE id=:id"), values).first():
            raise HTTPException(404, "Restaurant not found")
        db.execute(text("""
            INSERT INTO favorites VALUES (:uid,:id,:collection)
            ON CONFLICT(user_id,place_id) DO UPDATE SET collection=excluded.collection
        """), values)
    return {"ok": True}


@app.delete("/api/favorites/{place_id}")
def remove_favorite(place_id: str, account=Depends(auth.user)):
    with engine.begin() as db:
        db.execute(text("DELETE FROM favorites WHERE user_id=:uid AND place_id=:id"), {"uid": account["id"], "id": place_id})
    return {"ok": True}


class Chat(places.Search):
    question: str = Field(min_length=1, max_length=1500)
    provider: str = "search"
    conversation_id: Optional[str] = None


def owned(db, cid, account):
    if not account or not db.execute(text("SELECT id FROM conversations WHERE id=:id AND user_id=:uid"),
                                    {"id": cid, "uid": account["id"]}).first():
        raise HTTPException(404, "Conversation not found")


@app.post("/api/chat")
def chat(body: Chat, request: Request, account=Depends(auth.optional_user)):
    quota(request, account, "chat")
    if body.provider not in rag.providers():
        raise HTTPException(422, "Provider unavailable")
    cid = body.conversation_id
    if cid:
        with engine.connect() as db:
            owned(db, cid, account)
    rows = []
    if MODE == "demo" or body.dataset == "import":
        center, rows = places.search(body)
        rows = rag.constrain(body.question, rows, body, center)
    result = rag.answer(body.question, rows, body.provider)
    if account:
        with engine.begin() as db:
            if cid:
                owned(db, cid, account)
            else:
                cid = str(uuid4())
                db.execute(text("INSERT INTO conversations VALUES (:id,:uid,:title,:created)"),
                           {"id": cid, "uid": account["id"], "title": body.question[:100], "created": auth.now()})
            db.execute(text("INSERT INTO messages VALUES (:id,:cid,:payload,:created)"),
                       {"id": str(uuid4()), "cid": cid, "payload": json.dumps({"question": body.question, **result}),
                        "created": time.time_ns()})
    return {**result, "conversation_id": cid}


@app.get("/api/conversations")
def conversations(account=Depends(auth.user)):
    with engine.connect() as db:
        return db.execute(text("SELECT id,title,created FROM conversations WHERE user_id=:uid ORDER BY created DESC LIMIT 100"),
                          {"uid": account["id"]}).mappings().all()


@app.get("/api/conversations/{cid}")
def messages(cid: str, account=Depends(auth.user)):
    with engine.connect() as db:
        owned(db, cid, account)
        return [json.loads(row[0]) for row in db.execute(text("""
            SELECT payload FROM messages WHERE conversation_id=:id ORDER BY created
        """), {"id": cid})]


@app.delete("/api/conversations/{cid}")
def remove_conversation(cid: str, account=Depends(auth.user)):
    with engine.begin() as db:
        owned(db, cid, account)
        db.execute(text("DELETE FROM conversations WHERE id=:id AND user_id=:uid"), {"id": cid, "uid": account["id"]})
    return {"ok": True}


@app.post("/api/users/me/demo-reset")
def reset_demo(account=Depends(auth.user)):
    if MODE != "demo":
        raise HTTPException(403, "Demo reset is unavailable in live mode")
    with engine.begin() as db:
        params = {"uid": account["id"]}
        db.execute(text("""
            DELETE FROM favorites WHERE user_id=:uid AND place_id IN
            (SELECT id FROM restaurants WHERE source='demo')
        """), params)
        db.execute(text("DELETE FROM searches WHERE user_id=:uid"), params)
        db.execute(text("DELETE FROM conversations WHERE user_id=:uid"), params)
    return {"ok": True}


@app.get("/api/admin")
def system_overview(account=Depends(auth.admin)):
    with engine.connect() as db:
        plans = db.execute(text("SELECT plan,COUNT(*) AS count FROM accounts GROUP BY plan")).mappings().all()
        sources = db.execute(text("SELECT source,COUNT(*) AS count,MAX(updated) AS updated FROM restaurants GROUP BY source")).mappings().all()
        api_usage = db.execute(text("SELECT scope,period,count FROM counters WHERE scope='google:daily' ORDER BY period DESC LIMIT 30")).mappings().all()
        jobs = db.execute(text("""
            SELECT id,kind,state,attempts,error,index_status
            FROM jobs ORDER BY created DESC LIMIT 30
        """)).mappings().all()
    return {"health": health(), "plans": plans, "sources": sources, "api_usage": api_usage, "jobs": jobs}


class ImportBody(places.BaseModel):
    csv: str = Field(min_length=1, max_length=2_000_000)


@app.post("/api/admin/import", status_code=202)
def import_csv(body: ImportBody, account=Depends(auth.admin)):
    if MODE != "live":
        raise HTTPException(403, "Imports require the live environment")
    try:
        return worker.queue_import(body.csv)
    except (ValueError, csv.Error) as error:
        raise HTTPException(422, str(error))


@app.post("/api/admin/jobs/{job_id}/retry")
def retry_import(job_id: str, account=Depends(auth.admin)):
    if MODE != "live" or not worker.retry(job_id):
        raise HTTPException(409, "Job is unavailable for retry")
    return {"ok": True}

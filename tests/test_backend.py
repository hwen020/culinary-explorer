import hashlib
import hmac
import json
import subprocess
import sys
import time
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from backend import auth, billing, index, places, rag, worker
from backend.db import engine
from backend.main import app


@pytest.fixture
def client():
    with TestClient(app) as current:
        yield current


def login(client):
    data = {"email": uuid4().hex + "@example.test", "password": "a test password only"}
    assert client.post("/api/auth/register", json=data).status_code == 201
    response = client.post("/api/auth/login", json=data)
    assert response.status_code == 200
    assert "HttpOnly" in response.headers["set-cookie"]
    return response.json()["id"]


def test_auth_isolation_and_logout(client):
    assert client.get("/api/favorites").status_code == 401
    login(client)
    assert client.get("/api/admin").status_code == 403
    assert client.put("/api/favorites/demo-0", json={"collection": "Weekend"}).status_code == 200
    chat = client.post("/api/chat", json={"question": "What is nearby?"}).json()
    cid = chat["conversation_id"]
    assert client.get("/api/conversations/" + cid).json()[0]["evidence"] == []
    assert client.post("/api/auth/logout", headers={"Origin": "https://example.test"}).status_code == 403
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/users/me").status_code == 401
    login(client)
    assert client.get("/api/favorites").json() == []
    assert client.get("/api/conversations/" + cid).status_code == 404


def test_search_radius_cuisine_rating_price_and_csv(client):
    query = {"radius": 1, "unit": "km", "cuisine": "Chinese", "rating": 4.7, "price": 2}
    result = client.post("/api/search", json=query).json()
    assert [item["id"] for item in result["items"]] == ["demo-0"]
    for change in ({"radius": 0.1}, {"rating": 4.8}, {"price": 3}, {"cuisine": "Japanese"}):
        assert client.post("/api/search", json={**query, **change}).json()["items"] == []
    export = client.post("/api/restaurants/export", json=query)
    assert "text/csv" in export.headers["Content-Type"]
    assert "Sample Noodle House" in export.text
    assert "Sample Sushi Kitchen" not in export.text
    assert client.post("/api/search", json={"center": {"lat": 91, "lng": 0}}).status_code == 422


def raw_place(identity="place-1", lat=34.14):
    return {"id": identity, "displayName": {"text": " Test venue "}, "types": ["japanese_restaurant", "restaurant"],
            "location": {"latitude": lat, "longitude": -118.01}}


def test_google_pages_missing_fields_and_deduplication(monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "fake-key")
    pages = iter([{"places": [raw_place(), raw_place("invalid", 93)], "nextPageToken": "second"},
                  {"places": [raw_place(), raw_place("outside", 50)]}])
    monkeypatch.setattr(places, "request_google", lambda *args, **kwargs: next(pages))
    [(place, raw)] = places.discover(places.Point(lat=34.14, lng=-118.01), 2)
    assert place.name == "Test venue" and place.cuisine == ["Japanese"]
    assert place.rating is None and place.price is None and place.reviews is None
    assert raw["displayName"]["text"] == " Test venue "


def test_google_retries_and_error(monkeypatch, client):
    attempts = []
    def outage(**kwargs):
        attempts.append(kwargs)
        return httpx.Response(503)
    monkeypatch.setattr(places.httpx, "request", outage)
    monkeypatch.setattr(places.time, "sleep", lambda _: None)
    with pytest.raises(places.HTTPException) as failure:
        places.request_google("https://example.test", method="GET")
    assert failure.value.status_code == 503 and len(attempts) == 3


def test_worker_import_and_update(client):
    header = "id,name,lat,lng,cuisine,rating\n"
    data = header + "import-1,Old Name,34.14,-118.01,Japanese,\nimport-1,New Name,34.14,-118.01,Japanese,\n"
    assert worker.queue_import(data)["records"] == 1
    assert worker.tick()
    assert client.get("/api/restaurants/import-1").json()["name"] == "New Name"
    assert len(client.post("/api/search", json={}).json()["items"]) == 6
    with pytest.raises(ValueError):
        worker.queue_import(header + "bad,Invalid,95,-118.01,Japanese,")


def test_persistent_index_and_idempotent_reimport(client):
    csv = "id,name,lat,lng,cuisine\npersistent-1,Fixture Soba,34.14,-118.01,Japanese\n"
    first = worker.queue_import(csv)
    assert worker.tick()
    before = client.get("/api/restaurants/persistent-1").json()
    second = worker.queue_import(csv)
    assert worker.tick()
    assert client.get("/api/restaurants/persistent-1").json() == before
    with engine.connect() as db:
        for ticket in (first, second):
            assert db.execute(text("SELECT index_status FROM jobs WHERE id=:id"), ticket).scalar() == "indexed"
    result = subprocess.run([sys.executable, "-c", """
from backend.index import imported_evidence
from backend.places import Restaurant
record = Restaurant(id='persistent-1', name='Fixture Soba', lat=34.14, lng=-118.01, source='import')
docs = imported_evidence('Soba', [record])
assert len(docs) == 1 and docs[0].metadata['place_id'] == record.id
"""], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr


def test_retry_failed_index_job(client, monkeypatch):
    csv = "id,name,lat,lng\nretry-1,Retry Fixture,34.14,-118.01\n"
    job = worker.queue_import(csv)
    original = index.upsert
    def failed(*args):
        raise OSError("simulated indexing outage")
    monkeypatch.setattr(index, "upsert", failed)
    for _ in range(3):
        assert worker.tick()
        with engine.begin() as db:
            db.execute(text("UPDATE jobs SET available=0 WHERE id=:id"), job)
    assert client.get("/api/restaurants/retry-1").status_code == 404
    assert worker.retry(job["id"])
    monkeypatch.setattr(index, "upsert", original)
    assert worker.tick()
    assert client.get("/api/restaurants/retry-1").status_code == 200


def test_demo_reset_isolates_other_accounts_and_imports(client):
    imported = worker.queue_import("id,name,lat,lng\nreset-import,Authorized Fixture,34.14,-118.01\n")
    assert imported["records"] == 1 and worker.tick()
    client2 = TestClient(app)
    login(client2)
    login(client)
    for actor in (client, client2):
        assert actor.put("/api/favorites/demo-0", json={}).status_code == 200
        assert actor.post("/api/chat", json={"question": "Lunch options"}).status_code == 200
    assert client.put("/api/favorites/reset-import", json={}).status_code == 200
    assert client.post("/api/search", json={}).status_code == 200
    assert client.post("/api/users/me/demo-reset").status_code == 200
    assert [item["id"] for item in client.get("/api/favorites").json()] == ["reset-import"]
    assert client.get("/api/conversations").json() == []
    assert client.get("/api/users/me").json()["searches"] == []
    assert len(client2.get("/api/favorites").json()) == 1
    assert len(client2.get("/api/conversations").json()) == 1
    assert client.get("/api/restaurants/reset-import").status_code == 200
    assert client.get("/api/restaurants/demo-0").status_code == 200


def test_google_content_cannot_be_exported_or_indexed(client, monkeypatch):
    monkeypatch.setattr("backend.main.MODE", "live")
    assert client.post("/api/restaurants/export", json={}).status_code == 403
    with pytest.raises(ValueError, match="not authorized"):
        with index.store("google"):
            pass


def test_semantic_retrieval_and_unsupported_claims(client, monkeypatch):
    from langchain_core.embeddings import Embeddings

    class TestEmbeddings(Embeddings):
        def embed_documents(self, texts):
            return [self.embed_query(value) for value in texts]

        def embed_query(self, value):
            return [1.0, 0.0] if "Japanese" in value else [0.0, 1.0]

    _, records = places.search(places.Search())
    embeddings = TestEmbeddings()
    docs = rag.retrieve("Japanese", records, embeddings)
    assert docs[0].metadata["place_id"] == "demo-1"

    class Model:
        def with_structured_output(self, *args, **kwargs):
            return self

        def invoke(self, messages):
            return {"parsed": rag.Selection(ids=self.ids), "raw": SimpleNamespace(usage_metadata={"total_tokens": 8})}

    mock = Model()
    mock.ids = ["demo-1"]
    monkeypatch.setattr(rag, "embeddings", lambda: embeddings)
    monkeypatch.setattr(rag, "model", lambda provider: mock)
    ground = rag.answer("Japanese", records, "ollama")
    assert ground["mode"] == "ollama" and [row["id"] for row in ground["references"]] == ["demo-1"]
    mock.ids = ["invented restaurant"]
    result = rag.answer("Japanese", records, "ollama")
    assert result["mode"] == "search" and "invented restaurant" not in result["answer"]
    monkeypatch.setattr(rag, "model", lambda _: (_ for _ in ()).throw(TimeoutError()))
    assert rag.answer("Japanese", records, "ollama")["mode"] == "search"


def test_stripe_checkout_signed_lifecycle_and_quota(client, monkeypatch):
    import stripe

    uid = login(client)
    customer = "cus_test_" + uid
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_fixture")
    monkeypatch.setenv("STRIPE_STANDARD_PRICE_ID", "price_standard")
    monkeypatch.setenv("STRIPE_PREMIUM_PRICE_ID", "price_premium")
    monkeypatch.setenv("FREE_SEARCH_DAILY", "1")
    monkeypatch.setenv("STANDARD_SEARCH_DAILY", "4")
    monkeypatch.setattr(billing, "stripe_sdk", lambda: stripe)
    monkeypatch.setattr(stripe.Customer, "create", lambda **kwargs: SimpleNamespace(id=customer))
    monkeypatch.setattr(stripe.checkout.Session, "list", lambda **kwargs: SimpleNamespace(data=[]))
    monkeypatch.setattr(stripe.checkout.Session, "create", lambda **kwargs: SimpleNamespace(url="https://checkout.stripe.com/test-fixture"))
    current = []
    monkeypatch.setattr(stripe.Subscription, "list", lambda **kwargs: SimpleNamespace(auto_paging_iter=lambda: iter(current)))
    assert client.post("/api/billing/checkout", json={"plan": "standard"}).json()["url"].endswith("test-fixture")
    assert client.get("/api/users/me").json()["plan"] == "free"
    assert client.post("/api/search", json={}).status_code == 200
    assert client.post("/api/search", json={}).status_code == 429

    def event(event_type, event_id, sign=True):
        body = json.dumps({"id": event_id, "object": "event", "type": event_type, "livemode": False,
                           "data": {"object": {"customer": customer}}})
        timestamp = int(time.time())
        signature = hmac.new(b"whsec_fixture", f"{timestamp}.{body}".encode(), hashlib.sha256).hexdigest()
        return client.post("/api/billing/webhook", content=body,
                           headers={"stripe-signature": f"t={timestamp},v1={signature if sign else 'wrong'}"})

    current.append({"status": "active", "items": {"data": [{"price": {"id": "price_standard"}}]}})
    eid = "evt_" + uid
    assert event("customer.subscription.created", eid, False).status_code == 400
    assert event("customer.subscription.created", eid).status_code == 200
    assert event("customer.subscription.created", eid).status_code == 200
    assert client.get("/api/users/me").json()["plan"] == "standard"
    assert client.post("/api/search", json={}).status_code == 200
    current[0]["status"] = "past_due"
    assert event("invoice.payment_failed", eid + "_failed").status_code == 200
    assert client.get("/api/users/me").json()["subscription_status"] == "past_due"
    current[0]["status"] = "canceled"
    assert event("customer.subscription.deleted", eid + "_cancel").status_code == 200
    assert client.get("/api/users/me").json()["plan"] == "free"
    assert client.post("/api/search", json={}).status_code == 429

import csv
import io
import json
import logging
import os
import signal
import time
from pathlib import Path
from threading import Event
from uuid import uuid4

from sqlalchemy import text

from .auth import now
from .db import engine, migrate
from . import index
from .places import Restaurant, save

log = logging.getLogger(__name__)


def queue_import(content):
    reader = csv.DictReader(io.StringIO(content))
    if not reader.fieldnames or not {"id", "name", "lat", "lng"}.issubset(reader.fieldnames):
        raise ValueError("CSV requires id, name, lat, and lng headers")
    records = {}
    for index, raw in enumerate(reader, start=2):
        if index > 2001:
            raise ValueError("Import at most 2,000 records per job")
        if raw.get("source") not in (None, "", "import"):
            raise ValueError(f"Row {index} is not an authorized import record")
        data = {field: raw[field].strip() for field in Restaurant.model_fields
                if field not in {"source", "updated"} and isinstance(raw.get(field), str) and raw[field].strip()}
        for field in ("cuisine", "hours"):
            data[field] = [label.strip() for label in data.get(field, "").split("|") if label.strip()]
        try:
            place = Restaurant(**data, source="import")
        except ValueError as error:
            raise ValueError(f"Invalid restaurant at row {index}") from error
        records[place.id] = (place.model_dump(), raw)
    if not records:
        raise ValueError("CSV contains no rows")
    jid = str(uuid4())
    with engine.begin() as db:
        db.execute(text("INSERT INTO jobs (id,kind,payload,state,available,created) VALUES (:id,'import',:payload,'queued',:now,:now)"),
                   {"id": jid, "payload": json.dumps(list(records.values())), "now": now()})
    return {"id": jid, "records": len(records)}


def tick():
    with engine.begin() as db:
        job = db.execute(text("""
            UPDATE jobs SET state='running',index_status='indexing',attempts=attempts+1,available=:lease
            WHERE id=(SELECT id FROM jobs WHERE state IN ('queued','running') AND available<=:now ORDER BY created,id LIMIT 1)
            AND state IN ('queued','running') AND available<=:now
            RETURNING *
        """), {"lease": now() + 120, "now": now()}).mappings().first()
    if not job:
        return False
    gate = {"id": job["id"], "attempt": job["attempts"]}
    try:
        if job["attempts"] > 3 or job["kind"] != "import":
            raise ValueError("Job exceeded its retry limit or has an unsupported type")
        with engine.begin() as db:
            complete = db.execute(text("UPDATE jobs SET state='done',index_status='indexed',payload='[]',error=NULL WHERE id=:id AND attempts=:attempt"), gate)
            if complete.rowcount:
                indexable = []
                for record, raw in json.loads(job["payload"]):
                    place = Restaurant(**record)
                    if place.source != "import":
                        raise ValueError("Only authorized imports can be indexed")
                    source = db.execute(text("SELECT source FROM restaurants WHERE id=:id"), {"id": place.id}).scalar()
                    if source not in {None, "import"}:
                        raise ValueError("Imported identifier collides with another source")
                    save(db, place, raw)
                    indexable.append(place)
                with index.store("import") as index_store:
                    index.upsert(indexable, index_store)
    except Exception:
        log.exception("Import job failed")
        with engine.begin() as db:
            db.execute(text("UPDATE jobs SET state=:state,index_status=:state,available=:next,error='Import or indexing failed' WHERE id=:id AND attempts=:attempt"),
                       {**gate, "state": "failed" if job["attempts"] >= 3 else "queued", "next": now() + 15 * job["attempts"]})
    return True


def retry(job_id):
    with engine.begin() as db:
        return bool(db.execute(text("""
            UPDATE jobs SET state='queued',index_status='pending',attempts=0,available=:now,error=NULL
            WHERE id=:id AND kind='import' AND state='failed'
        """), {"id": job_id, "now": now()}).rowcount)


def cleanup():
    with engine.begin() as db:
        for table in ("sessions", "action_tokens"):
            db.execute(text(f"DELETE FROM {table} WHERE expires<=:now"), {"now": now()})
        db.execute(text("DELETE FROM counters WHERE period<:cutoff"), {"cutoff": now() - 31 * 86400})


def run():
    logging.basicConfig(level=logging.INFO)
    migrate()
    last_cleanup = 0
    heartbeat = os.getenv("WORKER_HEARTBEAT_FILE")
    stop = Event()
    signals = [signal.SIGINT, signal.SIGTERM]
    if hasattr(signal, "SIGBREAK"):
        signals.append(signal.SIGBREAK)
    for sig in signals:
        signal.signal(sig, lambda *_: stop.set())
    try:
        while not stop.is_set():
            if now() - last_cleanup >= 60:
                cleanup()
                if heartbeat:
                    Path(heartbeat).touch()
                last_cleanup = now()
            if not tick():
                stop.wait(2)
    finally:
        engine.dispose()


if __name__ == "__main__":
    run()

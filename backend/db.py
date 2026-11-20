import os
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv
from sqlalchemy import create_engine, event
from sqlalchemy.pool import NullPool
from sqlalchemy.engine import make_url

load_dotenv()
MODE = os.getenv("CULINARY_MODE", "demo")
DEPLOYMENT = os.getenv("CULINARY_DEPLOYMENT", "development")
if MODE not in {"demo", "live"}:
    raise RuntimeError("CULINARY_MODE must be demo or live")
if DEPLOYMENT not in {"development", "staging", "production"}:
    raise RuntimeError("CULINARY_DEPLOYMENT must be development, staging, or production")
data_root = Path(os.getenv("CULINARY_DATA_DIR", "data"))
directory = data_root / MODE
url = os.getenv("CULINARY_" + MODE.upper() + "_DATABASE_URL") or f"sqlite:///{directory / 'explorer.db'}"

if DEPLOYMENT == "production":
    origin = urlsplit(os.getenv("APP_ORIGIN", ""))
    if (MODE != "live" or origin.scheme != "https" or not origin.hostname or origin.username is not None
            or origin.path not in {"", "/"} or origin.query or origin.fragment):
        raise RuntimeError("Production requires live mode and an HTTPS APP_ORIGIN")
    if os.getenv("ADMIN_EMAILS") or os.getenv("CULINARY_DEMO_DATABASE_URL"):
        raise RuntimeError("Production requires separate administrator and database settings")
    if any(os.getenv(name) for name in ("STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET",
                                        "STRIPE_STANDARD_PRICE_ID", "STRIPE_PREMIUM_PRICE_ID")):
        raise RuntimeError("Stripe billing is available only in staging or development")
    target = make_url(url)
    if target.get_backend_name() == "sqlite":
        database = target.database
        if not database or database == ":memory:" or target.query:
            raise RuntimeError("Production SQLite requires a persistent file")
        if (data_root / "demo").resolve() in Path(database).resolve().parents:
            raise RuntimeError("Production SQLite cannot use the demo directory")

directory.mkdir(parents=True, exist_ok=True)
pool_options = {"poolclass": NullPool} if url.startswith("sqlite:///") and not url.endswith("/:memory:") else {}
engine = create_engine(url, pool_pre_ping=True, **pool_options)

if engine.dialect.name == "sqlite":
    @event.listens_for(engine, "connect")
    def configure_sqlite(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=5000")


def migrate():
    from sqlalchemy import text

    with engine.begin() as connection:
        if engine.dialect.name == "postgresql":
            connection.execute(text("SELECT pg_advisory_xact_lock(981604)"))
        elif engine.dialect.name == "sqlite":
            connection.execute(text("BEGIN IMMEDIATE"))
        connection.execute(text("CREATE TABLE IF NOT EXISTS schema_versions (name TEXT PRIMARY KEY)"))
        for path in sorted(Path(__file__).with_name("migrations").glob("*.sql")):
            if connection.execute(text("SELECT name FROM schema_versions WHERE name=:name"), {"name": path.name}).first():
                continue
            for statement in path.read_text(encoding="utf-8").split(";"):
                if statement.strip():
                    connection.execute(text(statement))
            connection.execute(text("INSERT INTO schema_versions VALUES (:name)"), {"name": path.name})

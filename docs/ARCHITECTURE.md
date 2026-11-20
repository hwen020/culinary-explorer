# Architecture

The React interface sends same-origin API requests through the Vite development proxy or nginx in Compose. FastAPI owns authentication, sessions, database authorization and subscription entitlements. OpenAPI is available by visiting `/docs` on the FastAPI listener.

SQLAlchemy applies the ordered migration files and records successful versions in `schema_versions`. SQLite takes an immediate transaction for migrations. PostgreSQL uses a transaction advisory lock. SQLite connections close when returned from database operations. The API and worker dispose their engines on shutdown.

Demo and live modes default to different SQLite databases. Demo accounts can reset their own conversations, searches and demo favorites.

The worker claims jobs with a deadline, validates the allowed source, writes restaurant rows and upserts persistent vectors by place ID. Import status is visible to verified administrators. Automatic retry handles transient failures, and an administrator can requeue a terminal failure. Older imports completed before vector indexing can be re-imported. The stable record ID and content comparisons make identical imports safe to repeat. A collection uses local feature hashing for lexical retrieval and runs without a model or API key. An optional LLM consumes retrieved IDs and the API checks all selections against SQL-filtered evidence.

Compose uses a dedicated Chroma service so database state can be shared across API and worker processes. Embedded Chroma is provided for single-process operation and tests. The demo model path, when explicitly configured outside the Windows launcher, can also use the original request-scoped semantic retrieval.

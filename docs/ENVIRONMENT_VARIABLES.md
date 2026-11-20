# Environment variables

Copy `.env.example` to `.env` when configuring manual startup or Compose. Leave credentials blank for the offline demo.

| Setting | Purpose |
|---|---|
| `CULINARY_MODE`, `CULINARY_DATA_DIR` | Select `demo` or `live` and the data root |
| `CULINARY_DEPLOYMENT` | `development` by default, `staging` for integration trials, `production` for HTTPS live mode with isolated administrator settings and billing disabled |
| `APP_ORIGIN`, `CULINARY_WEB_PORT` | External browser origin and Compose host port. If changing the port, set the origin to match |
| `CULINARY_LIVE_DATABASE_URL`, `CULINARY_DEMO_DATABASE_URL` | Separate optional database overrides. Use `postgresql+psycopg://` for PostgreSQL. Windows launcher and Compose keep demo on SQLite |
| `GOOGLE_MAPS_API_KEY`, `GOOGLE_BROWSER_KEY`, `GOOGLE_DAILY_REQUESTS` | Live discovery and Geocoding backend key, separately restricted Maps JavaScript browser key, request cap |
| `ADMIN_EMAILS`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_FROM`, `SMTP_USERNAME`, `SMTP_PASSWORD` | Verified administrator allowlist and optional STARTTLS email |
| `PRODUCTION_ADMIN_EMAILS` | Separate allowlist for verified production administrators. Keep `ADMIN_EMAILS` and the demo database override empty in production |
| `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_EMBEDDING_MODEL`, `EMBEDDINGS_PROVIDER` | Optional live model configuration. Persistent authorized-import vectors use offline hashing |
| `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `OLLAMA_EMBEDDING_MODEL` | Optional local model configuration |
| `CHROMA_HOST`, `CHROMA_PORT` | Shared index service for multiprocess ingestion and retrieval, configured internally by Compose |
| `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_STANDARD_PRICE_ID`, `STRIPE_PREMIUM_PRICE_ID` | Test-mode Stripe secret, verified event endpoint secret and separately configured recurring Prices |
| `FREE_SEARCH_DAILY` and corresponding plan/action variables | Server-side search and chat limits |

Set the Stripe webhook URL to `/api/billing/webhook` at the configured origin and subscribe to subscription lifecycle events, `invoice.payment_failed` and `invoice.paid`. Set up the Billing Portal in the same Stripe test environment. SMTP is required to verify live accounts. Keep API keys outside Git and restrict the browser key by approved origins and API.

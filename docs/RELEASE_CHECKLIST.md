# Phase 5 release checklist

## Frozen demo

- [x] The initial working tree was clean. The annotated local tag `v0.1.0-demo` points to `cb2c1bc718a43dd236885dcff3900f2b5710ea49`.
- [x] Keep existing data, configuration and the pre-baseline backup. Release preparation changes follow the frozen tag. No remote push, public release, or cloud resources were created.
- [x] Demo regression on Windows. Pytest 11, Vitest 2 and Playwright 2 passed. TypeScript, Vite production build and dependency checks passed.

## Container acceptance

- [x] Run `docker compose config --quiet` without printing interpolated secrets. The configuration passed.
- [ ] Restore Docker Desktop’s connection to its WSL 2 engine. Both Windows named-pipe contexts returned HTTP 500 before Compose could start an application. Forcing API v1.43 did not help. The Desktop backend reported `no route to host` when connecting to its private WSL engine endpoint. WSL lists the Docker distributions as running. These observations identify a host-to-engine connectivity failure. The underlying host networking fault is unresolved. Starting Docker Desktop normally did not restore connectivity.
- [ ] Arrange a Docker Desktop maintenance window, check for other active workloads, then use its normal restart and recheck `docker --context desktop-linux version`. Preserve volumes, images and both Docker WSL distributions. [Docker Desktop troubleshooting](https://docs.docker.com/desktop/troubleshoot-and-support/troubleshoot/)
- [ ] Once the engine responds, use separate demo and live release-check Compose project names and separate volumes. For the demo run `docker compose -p culinary-rc-demo up --build -d --wait`, check `ps`, `logs --tail 100` and `curl.exe --fail http://localhost:8080/api/health`, then repeat the browser workflow at that address. Set the appropriate origin and free port if another project is already listening. Leave all images and named volumes in place. Use `stop` for the release-check projects after validation.
- [ ] Capture account, favorite and conversation IDs before and after restarting the demo services. In a separate isolated live/staging stack, use an authorized fictional fixture to verify a worker import and Chroma retrieval before and after restart. Confirm the live stack rejects the demo identity and use `docker compose volumes` on supported versions or `docker volume ls` to inspect the named volumes. Container tests and restart persistence are **NOT TESTED** while the engine is unavailable.

## Production controls and credentials

The release-prep startup guard requires `CULINARY_DEPLOYMENT=production`, `CULINARY_MODE=live` and an HTTPS-only `APP_ORIGIN` for the production profile. It rejects a demo database override, SQLite under the demo directory, the development administrator allowlist and Stripe settings. Supply a verified production-specific administrator using `PRODUCTION_ADMIN_EMAILS`. Stripe currently operates in test mode in staging and development. Production starts with billing disabled.

| Item | Configuration and acceptance |
|---|---|
| Database | Use a separate Compose project and `/data` volume for production. With default SQLite, demo lives at `/data/demo/explorer.db` and live at `/data/live/explorer.db`. Optional PostgreSQL requires a distinct `CULINARY_LIVE_DATABASE_URL` and needs real server verification. |
| Index and worker | Chroma uses `/vectors`, internal DNS `chroma` and port 8001. The worker and API share `/data`; the worker heartbeat is runtime-only. Back up both persistent volumes and verify restoration before public release. |
| HTTPS and CORS | Terminate TLS at the ingress and keep frontend and `/api` on the same origin. Set `APP_ORIGIN` to that public origin. Confirm Secure cookies, exact-origin preflights, host and request-header behavior, and nginx/Uvicorn log handling at ingress. |
| Google | Optional `GOOGLE_MAPS_API_KEY` for Places and Geocoding, `GOOGLE_BROWSER_KEY` restricted to authorized Maps JavaScript origins, and `GOOGLE_DAILY_REQUESTS`. Verify attribution and terms before enabling. Google rows are blocked from CSV export and Chroma ingestion. [Google Places content policies](https://developers.google.com/maps/documentation/places/web-service/policies) |
| SMTP | For live verification and password reset, configure `SMTP_HOST`, `SMTP_PORT`, `SMTP_FROM`, and private `SMTP_USERNAME` and `SMTP_PASSWORD` if required. Test delivery and recovery before opening registration. |
| Models | Use `OPENAI_API_KEY` and model settings if approved, or configure `OLLAMA_BASE_URL`, `OLLAMA_MODEL` and `OLLAMA_EMBEDDING_MODEL` for local inference. Offline demo needs neither. |
| Stripe | Staging only. Use isolated test-account `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, and `STRIPE_STANDARD_PRICE_ID` and `STRIPE_PREMIUM_PRICE_ID`. Verify test event delivery and Billing Portal. A separate review is required for real payments. |

## Lowest-cost cloud options

| Platform | Structure | Persistence and worker limits |
|---|---|---|
| Render Free, quickest disposable demo | A free static frontend plus a free FastAPI web service. Use a static rewrite from `/api/*` to the API service and set `APP_ORIGIN` to the frontend HTTPS origin. Verify POST, cookies and cold-start behavior before any release. | SQLite files are ephemeral across spin-downs, restarts and redeploys. Free Postgres lasts 30 days, and PostgreSQL has yet to be verified here. Free web services sleep after 15 minutes without traffic. Render provides no free continuous background worker. [Render Free](https://render.com/docs/free) · [Render rewrites](https://render.com/docs/redirects-rewrites) · [Render worker limits](https://render.com/docs/migrate-from-heroku) |
| Railway Free, low-traffic persistent demo | Two services, frontend proxy and FastAPI, with a small volume at `/data` on the backend. A Railway-specific nginx upstream must point at the Railway private hostname and handle the platform port. Keep import jobs disabled in the demo. | Railway documents a monthly $1 usage allowance, 0.5 GB RAM per service, one 0.5 GB volume, and up to three services. Services sleep and stop if credit runs out. Four existing services and two volumes exceed the free structure; continuous worker availability is unsupported. [Railway Free plan](https://docs.railway.com/pricing/free-plan) |
| OCI Always Free, closest match for the full stack | One eligible Linux VM with Compose and an HTTPS reverse proxy. Keep SQLite and Chroma on persistent block storage. The same VM runs frontend, API, worker and Chroma without the developer’s computer. | Availability depends on region capacity and sufficient memory. Check image architecture compatibility, use only Always Free resources and keep off-host backups. Oracle may reclaim idle instances. [OCI Always Free resources](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm) |

Start with the Render option if a disposable portfolio preview is sufficient. Use Railway only if a low-traffic demo needs to keep accounts across restarts and its monthly quota is acceptable. Evaluate the OCI option for a continuously running import worker and persistent SQLite plus Chroma. These are preparation paths. No plan was activated and no cloud deployment or billing setup was performed.

## Minimum next stage

1. Restore host Docker connectivity and verify the four containers, browser workflow, post-restart persistence and volume backup/restore.
2. Select the desired persistence and uptime guarantees, then verify the corresponding staging configuration, HTTPS ingress, health, origin and cookies. Obtain explicit authorization before provisioning or publishing.
3. Configure only the external providers required for the release. Verify allowed Google usage, account email delivery and operational controls before opening public access.

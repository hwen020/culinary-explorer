# Docker deployment

Local default configuration uses Compose and a SQLite volume. A dedicated Chroma service keeps indexed files in a second volume. FastAPI, the worker and Chroma stay on the internal network. The frontend publishes a loopback port and proxies `/api/` to FastAPI.

```sh
docker compose config --quiet
docker compose up --build -d
docker compose ps
docker compose stop
```

The default browser address is `http://localhost:8080`. SQLite migrations run before the API serves requests. The worker waits for API health. API and worker share their SQLite volume, and changes use a transaction. Leave SQLite on a local filesystem and run a single worker per database for this configuration.

For a private staging deployment, set `APP_ORIGIN` to the externally visible HTTPS origin and route traffic through a TLS reverse proxy on the host. Store credentials in private environment configuration, restrict firewall access, configure independently verified administrators and SMTP, and back up both volumes before upgrades. Use database and vector snapshots from a quiescent stack. Stripe supports test keys only. PostgreSQL is an optional configuration via `CULINARY_LIVE_DATABASE_URL` and has not been exercised against a real server.

Set `CULINARY_DEPLOYMENT=production` together with `CULINARY_MODE=live` when validating a production startup. Use a distinct Compose project and separate persisted volumes. The production profile requires an HTTPS origin, uses `PRODUCTION_ADMIN_EMAILS` and rejects staging Stripe settings. See the [release checklist](RELEASE_CHECKLIST.md) for validation and cloud options.

Before public release, verify live service credentials, attribution and applicable usage terms, delivery and restore procedures, operational limits, and an authenticated deployment. Check [implementation status](IMPLEMENTATION_STATUS.md) for what ran in this workspace.

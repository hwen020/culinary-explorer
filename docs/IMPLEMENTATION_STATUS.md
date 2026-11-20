# Implementation status

## Phase 5 — Release candidate and cloud deployment readiness

The stable local release is the annotated tag `v0.1.0-demo` at `cb2c1bc`. The working tree was clean at freeze time. The production guard and release documentation follow the frozen tag. Existing data, backups and local configuration were retained. No remote release, provisioning or billing setup was performed.

| Check | Phase 5 result |
|---|---|
| Full local regression | **PASS**. Pytest 11, Vitest 2, Edge Playwright 2, TypeScript, Vite production build and Python dependency integrity. Playwright used local Vite preview and FastAPI. |
| Production startup and security | **PASS locally**. Uvicorn served health with HTTP 200, startup and access logs were captured, and the worker wrote its heartbeat. An isolated smoke test checked exact-origin CORS, Secure session cookies, admin denial, disabled billing, and rejection of unsafe production configurations. HTTPS ingress and container logs remain **NOT TESTED**. |
| Data isolation and persistence | **PASS locally**. The demo identity could not authenticate against live data. Independent Python processes reopened SQLite and Chroma and verified an account, favorite, conversation, authorized import and vector. Docker volume and restart persistence remain **NOT TESTED**. |
| Google boundaries | **PASS locally** for CSV export rejection and vector source guard. Live Google calls remain **SKIPPED**. |
| Docker | Compose configuration **PASS**. Docker Engine access **FAIL**. Desktop's API proxy reported no route to the WSL engine endpoint, including after a normal Desktop launch attempt. Image builds, container health checks, and the browser workflow at port 8080 are **NOT TESTED**. |
| Cloud | **NOT TESTED**. Render Free is viable for an ephemeral demo, Railway Free is a low-traffic volume-backed candidate, and an eligible OCI Always Free VM is the closest fit for the four-service Compose stack. |

Production uses an explicit deployment profile with HTTPS, an independently verified administrator allowlist and separate demo/live database settings. Stripe testing stays in staging. The [release checklist](RELEASE_CHECKLIST.md) records Docker recovery steps, required provider settings, cloud quotas and the remaining checks before public launch.

Verified in the existing Windows workspace on 2026-11-19. The React and FastAPI application runs locally in demo mode with no third-party credentials.

## Browser failure and fix

The original Edge trace showed pending `/api/health` and `/api/users/me` requests when the homepage assertion expired. FastAPI had already started. A second trace showed multi-second Vite development module loads and requests still pending at navigation timeout. The old test fixture waited for the Vite root page and the direct backend, leaving the proxied health route unchecked. The browser fixture now runs the actual production bundle with explicit IPv4 loopback listeners, verifies the API through the proxy, and uses a dedicated temporary SQLite database. The frontend exposes its initialization state and loads the profile after health resolves. The original demo assertion remains. Edge subsequently exposed an ambiguous price label and a login/navigation race, both addressed before the final run.

## Real local execution

| Check | Result |
|---|---|
| Pytest | **PASS**, 11 tests, 18.51 seconds. Pytest exited cleanly, including temporary SQLite and Chroma cleanup. |
| Vitest | **PASS**, 2 tests |
| TypeScript and Vite production build | **PASS**. Build output went to a temporary directory. |
| Playwright desktop and mobile | **PASS**, 2 tests, 20.2 seconds |
| Demo acceptance | **PASS**. Health and mode banner, registration, login, location and filters, map marker and details, favorite, CSV download, deterministic chat, reload and restored favorites and history, logout and protected endpoint checks, renewed login, mobile plans and viewport. Directions URL was verified without opening the external site. |
| FastAPI and Windows batch scripts | **PASS**. Start initialized dependencies, the proxied health check returned demo mode, search returned six fictional fixtures, repeated start reused the instance, and stop released both ports. Uvicorn logged graceful shutdown. |
| Database migrations | **PASS**. All three applied on a fresh local startup. Applying twice to a copy of the previous development database preserved record counts, and integrity returned `ok`. |
| CSV worker and Chroma persistence | **PASS**. Re-import preserved result identity and change timestamp. A fresh Python process retrieved the persistent vector. A simulated indexing failure exercised retries and manual requeue. |
| Demo reset and Google source boundaries | **PASS**. Reset preserved another demo account’s activity and an authorized import. Live Places content is blocked from export and indexing. |
| Dependency integrity | **PASS**, `pip check` reported no broken requirements |
| ESLint | **NOT TESTED**. ESLint is unconfigured. |
| Compose configuration | **PASS**, `docker compose config --quiet` |
| Docker images and runtime | **NOT TESTED**. Both local Docker Engine endpoints returned HTTP 500. |

## External verification

| Service | Result |
|---|---|
| Google Places | **MOCK PASS** for paging, retry, deduplication and missing fields. **SKIPPED** for live discovery without a backend Maps key. |
| Google Maps JavaScript | **SKIPPED** without a browser key. The illustrative demo map ran in Edge. |
| Stripe | **MOCK PASS** for signed webhooks, lifecycle and quotas. **SKIPPED** for real test-account Checkout and Portal without test keys, webhook secret and Price IDs. |
| SMTP | **SKIPPED** without a configured mail relay. |
| OpenAI and Ollama | **MOCK PASS** for provider response validation and fallback. **SKIPPED** for live inference without an API key or configured local models. |
| PostgreSQL | **NOT TESTED**. SQLite is the verified default. |

Windows access is `http://localhost:5173` after `start_windows.bat`. Compose is configured for `http://localhost:8080`. The project is ready for local demonstrations. Public deployment still requires container smoke testing, live provider verification, Google attribution and terms review, and operational validation.

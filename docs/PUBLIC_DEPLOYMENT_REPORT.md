# GitHub publication and hosted preview

Public acceptance verified 2026-11-20. [Live Demo](https://culinary-explorer-demo.onrender.com).

| Item | Result |
|---|---|
| Public repository | **PASS**. [hwen020/culinary-explorer](https://github.com/hwen020/culinary-explorer), default branch `main`. [Latest remote commit](https://github.com/hwen020/culinary-explorer/commits/main/). |
| Remote file audit | **PASS**. README, MIT LICENSE, both Demo screenshots and preview configuration are present. The push contains only the clean public history. |
| GitHub Actions | Baseline **PASS**. See the [hosted run for the published baseline](https://github.com/hwen020/culinary-explorer/actions/runs/44796913903) and [the latest hosted run](https://github.com/hwen020/culinary-explorer/actions). |
| Render service | **PASS** for a reachable public service at `culinary-explorer-demo.onrender.com`. The deployed account plan is **pending manual confirmation**. The repository Blueprint declares a single Free web service. Dashboard or billing access was unavailable. |
| Public HTTPS | **PASS**. The homepage and `/api/health` returned HTTP 200 with successful certificate verification. Health reported Demo preview mode, deterministic search, and an empty Maps key. The observed 0.38 s homepage and 0.28 s health responses are request timings, not confirmed cold-start measurements. |
| Public Playwright | **PASS**. Two Edge tests ran against the public HTTPS service, plus a separate complete mobile workflow at a 390 px viewport. Verified six fictional rows, filters, the illustrative map, favorites, deterministic chat, history after reload, CSV download and its one fictional data row, guest isolation, and Secure/HttpOnly/SameSite=Lax cookies. |
| Browser and network diagnostics | **PASS**. The mobile workflow recorded no JavaScript errors, unexpected console errors, transport failures, HTTP 5xx or cross-origin application requests. The initial unsigned profile request returned the expected HTTP 401. Render server logs were unavailable. |
| Local preview Playwright | **PASS**, 2 Edge tests. Verified guest entry, search and filters, fictional map, CSV export, saved favorites and chat history, isolation, request size limit, disabled providers and sensitive endpoints, SPA refresh and mobile viewport. |
| Local full mode | **PASS**, 11 Pytest tests, 2 Vitest tests, TypeScript/Vite build, and 2 Edge Playwright tests. Production still rejects Demo mode. |
| Local preview reset | **PASS**. A fresh process rejected the previous session and seeded six fictional rows. New sessions started with empty favorites. |
| Render memory, cold start, and service restart | **NOT TESTED**. A hosted restart or confirmed sleep transition was not under this session?s control. Browser reload retained active guest state. Separate GitHub runner and local process tests confirmed reseeding and old-session invalidation after process restart. |

The [initial hosted container run](https://github.com/hwen020/culinary-explorer/actions/runs/44797437372) built the Docker image but failed when the port briefly reset the first health request. The readiness check now retries that transient error. The [corrected resource-limited runner test](https://github.com/hwen020/culinary-explorer/actions/runs/44797842520) records container readiness timing, memory and restart behavior in its logs. Runner observations do not measure Render itself.

## Preview behavior

One FastAPI service hosts the React assets and API on a single origin. Anonymous guest sessions store temporary activity in isolated SQLite. Sessions expire after two hours and process replacement clears state, including history and favorites. An ephemeral restart seeds the same fictional restaurants again.

The preview uses deterministic demonstration recommendations and an illustrative map. Admin, arbitrary uploads, billing, email, external directions and real data providers are unavailable. It needs no background worker, Chroma index, hosted database or paid credentials. The regular local and live configurations remain separate.

The [public demo guide](PUBLIC_DEMO.md) records the Free Blueprint and acceptance commands. Verify the current compute plan in the Render dashboard. A controlled restart or observed sleep/wake cycle is still needed to verify session reset on Render itself.

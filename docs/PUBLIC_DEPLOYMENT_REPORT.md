# GitHub publication and hosted preview

Verified 2026-11-20.

| Item | Result |
|---|---|
| Public repository | **PASS**. [hwen020/culinary-explorer](https://github.com/hwen020/culinary-explorer), default branch `main`. [Latest remote commit](https://github.com/hwen020/culinary-explorer/commits/main/). |
| Remote file audit | **PASS**. README, MIT LICENSE, both Demo screenshots and preview configuration are present. The push contains only the clean public history. |
| GitHub Actions | Baseline **PASS**. See the [hosted run for the published baseline](https://github.com/hwen020/culinary-explorer/actions/runs/44796913903) and [the latest hosted run](https://github.com/hwen020/culinary-explorer/actions). |
| Render | **SKIPPED**. No usable Render account authorization was available. The Blueprint defines one Free web service named `culinary-explorer-demo`, with no attached paid resources. |
| Public HTTPS URL and public Playwright | **NOT TESTED**. No Render instance was provisioned and no verified Demo URL exists. |
| Local preview Playwright | **PASS**, 2 Edge tests. Verified guest entry, search and filters, fictional map, CSV export, saved favorites and chat history, isolation, request size limit, disabled providers and sensitive endpoints, SPA refresh and mobile viewport. |
| Local full mode | **PASS**, 11 Pytest tests, 2 Vitest tests, TypeScript/Vite build, and 2 Edge Playwright tests. Production still rejects Demo mode. |
| Local preview reset | **PASS**. A fresh process rejected the previous session and seeded six fictional rows. New sessions started with empty favorites. |
| Render memory, cold start, and recovery | **NOT TESTED**. The selected Free plan has 512 MB RAM. Platform wake-up, sustained load and restart behavior need a real service. |

The [initial hosted container run](https://github.com/hwen020/culinary-explorer/actions/runs/44797437372) built the Docker image but failed when the port briefly reset the first health request. The readiness check now retries that transient error. The [corrected resource-limited runner test](https://github.com/hwen020/culinary-explorer/actions/runs/44797842520) records container readiness timing, memory and restart behavior in its logs. Runner observations do not measure Render itself.

## Preview behavior

One FastAPI service hosts the React assets and API on a single origin. Anonymous guest sessions store temporary activity in isolated SQLite. Sessions expire after two hours and process replacement clears state, including history and favorites. An ephemeral restart seeds the same fictional restaurants again.

The preview uses deterministic demonstration recommendations and an illustrative map. Admin, arbitrary uploads, billing, email, external directions and real data providers are unavailable. It needs no background worker, Chroma index, hosted database or paid credentials. The regular local and live configurations remain separate.

To finish activation, use the [Render Blueprint](https://render.com/deploy?repo=https://github.com/hwen020/culinary-explorer), sign in, connect the GitHub repository, and verify the planned service is **Free** before applying. Run the HTTPS acceptance suite and record the resulting service URL using the [public demo guide](PUBLIC_DEMO.md).

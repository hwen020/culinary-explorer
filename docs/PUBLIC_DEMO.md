# Public preview on Render

Run a single free Web Service using the repository's `render.yaml` Blueprint. It declares a Docker web service, the Free plan, and `/api/health`. In the Render Dashboard, authorize the GitHub integration for this repository, choose **New > Blueprint**, select the repository and confirm the plan is **Free** before applying. Add no databases, disks, workers, domains or provider keys. The managed HTTPS URL is supplied to the application by Render.

The Docker build compiles React in a separate stage. The runtime starts one Uvicorn process on Render's `PORT`, with static assets and API on one origin. The app uses the canonical external URL for mutation-origin checks and secure cookies. It does not trust caller-supplied forwarded headers. The build intentionally omits Chroma and optional LLM SDKs from this runtime because the fictional preview uses exact filters and deterministic ranking without a model. Existing Windows, Compose and live development entry points remain available.

Guest sessions require no email and expire after two hours. They use isolated temporary SQLite and can reset on restarts or free-instance sleep. Fixtures are seeded again on startup. Session capacity, aggregate request rate, concurrency and request bodies are bounded. Real providers, administration, file imports and checkout are unavailable. The front end displays a reset warning and asks guests to use fictional information only.

## Local same-origin check

Build with `npm ci` and `npm run build`. From PowerShell with the Python environment active, run:

```powershell
$env:CULINARY_TEST_PYTHON = (Get-Command python).Source
$env:CULINARY_BROWSER = 'msedge'
npx playwright test --config playwright.preview.config.ts
```

To verify a deployed instance run the same command with `CULINARY_PREVIEW_URL` set to the actual HTTPS service origin. After a controlled service restart, check that the first response becomes healthy, the fictional fixtures are available, and a previously valid guest cookie no longer exposes old state. Capture memory metrics and cold-start duration from the deployed service before recording them as verified.

See [Render Free limitations](https://render.com/docs/free) and [Blueprint reference](https://render.com/docs/blueprint-spec).

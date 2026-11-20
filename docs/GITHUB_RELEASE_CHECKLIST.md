# GitHub public release checklist

**READY for a GitHub Public Repository as an audited source-only snapshot.**

The snapshot was exported from source revision `d45c00c` on 2026-11-20. The supplied Streamlit entry point and its legacy database migration helper were excluded. The React and FastAPI application does not depend on either. The public repository starts with a fresh root commit. The original project and its `v0.1.0-demo` tag remain in the original repository.

## Release audit

- The committed source contains 59 files. Each file was matched against the reviewed export, with changes limited to release documentation and the obsolete Streamlit ignore entry.
- No original proposal PDF, private environment file, keys, database, account data, uploads, backups, or browser artifacts were included. The tracked environment example contains blank credential values.
- The MIT license covers original project contributions for which the contributors hold redistribution rights. No third-party packages or browser binaries are bundled; see [third-party notices](THIRD_PARTY_NOTICES.md).
- The two screenshots match the previously visually reviewed credential-free Demo captures. They contain fictional restaurant rows and an illustrative map.
- The README links and GitHub Actions file and command references resolve in this snapshot. Hosted GitHub Actions has not run.

## Local verification in this snapshot

| Check | Result |
|---|---|
| Pytest | PASS, 11 tests |
| Vitest | PASS, 2 tests |
| TypeScript and Vite production build | PASS |
| Edge Playwright | PASS, 2 tests |
| Production security | PASS in local smoke checks for production startup guards, HTTPS origin, Secure cookies, CORS, administrator authorization, billing settings, and Google CSV export restrictions |
| Docker runtime | NOT TESTED |
| Google Places, models, and Stripe | MOCK PASS where covered. Live providers were not verified. |

This release can be published as source code and a credential-free local demo. The audit was completed before publication. See the [deployment report](PUBLIC_DEPLOYMENT_REPORT.md) for the current public repository and hosted verification status.

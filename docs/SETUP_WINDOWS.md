# Windows and VS Code

Install 64-bit Python 3.12 with the Python launcher and Node.js 20 or later. From the project directory run `start_windows.bat`. The script uses an existing Python 3.12 environment or creates `.venv312`. It installs pinned Python packages and uses `npm ci` with the committed lockfile. The first run requires package registry access.

Open `http://localhost:5173`. FastAPI listens on `127.0.0.1:8000`. The supervisor starts FastAPI, the worker and Vite, checks the API through the frontend proxy and records local logs under `.local-run/`. A second invocation reports the same address. `stop_windows.bat` requests shutdown of the owned services and waits for exit. SQLite records persist under `data/demo/` by default. An existing `.env` is kept intact. The launcher selects demo mode and disables optional model access.

For manual startup, use a PowerShell terminal in this directory.

```powershell
py -3.12 -m venv .venv312
.\.venv312\Scripts\python.exe -m pip install -r requirements-lock.txt
npm.cmd ci
if (!(Test-Path .env)) { Copy-Item .env.example .env }
```

Then start each command in its own terminal. For the demo, leave `APP_ORIGIN` at its localhost default and use `CULINARY_MODE=demo`.

```powershell
.\.venv312\Scripts\python.exe -m uvicorn backend.main:app --port 8000
.\.venv312\Scripts\python.exe -m backend.worker
npm.cmd run dev
```

In VS Code, run the **Start Culinary Explorer** or **Stop Culinary Explorer** task. **React browser (debug)** starts the launcher and opens Edge. To debug FastAPI separately, stop the launcher, select the Python 3.12 environment, run **FastAPI demo (debug)** and start Vite in a separate terminal.

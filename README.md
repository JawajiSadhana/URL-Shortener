# URL Shortener AI

A FastAPI-based URL shortening service with admin protection, analytics, observability, and Docker support.

## Environment Setup

The application reads configuration from a `.env` file. A sample configuration is provided in `.env.example`.

### Required variables

- `BASE_URL`: The public URL base for shortened links (e.g. `http://localhost:8000`).
- `ADMIN_API_KEY`: Secret API key for admin access.
- `DB_URL`: Database connection string.
- `CORS_ORIGINS`: Allowed CORS origins.
- `SLUG_LENGTH`: Default slug length for generated short URLs.

### Admin API Key

The admin dashboard is protected by `ADMIN_API_KEY`.

1. Copy `.env.example` to `.env`:

```bash
copy .env.example .env
```

2. Update `ADMIN_API_KEY` in `.env` with a strong random string:

```env
ADMIN_API_KEY=your_secret_key_here
```

3. Use the same key when accessing admin routes.

### Accessing Admin

Protect admin routes with either:

- `X-API-Key` request header
- `admin_api_key` cookie

Example with `curl`:

```bash
curl -H "X-API-Key: your_secret_key_here" http://localhost:8000/admin
```

## Running Locally

Install dependencies:

```bash
pip install -r requirements.txt
```

Start the app:

```bash
uvicorn app.main:app --reload
```

Open `http://localhost:8000` in your browser.

## Demo runs (agent end-to-end)

A small demo runner exercises the agent orchestration, approval flow, executor, and reviewer end-to-end.

- Script: `scripts/demo_runs.py`
- Purpose: runs three orchestrations:
	- Greenfield run (execute planner output without approval)
	- Brownfield run (create pending approval, then approve and execute)
	- Brownfield run with clarifying question (reject with comment, then approve)

How to run (from project root):

PowerShell:

```powershell
$env:PYTHONPATH='.'; python scripts/demo_runs.py
```

Linux/macOS (bash):

```bash
PYTHONPATH=. python3 scripts/demo_runs.py
```

The script uses the FastAPI TestClient and prints logs showing planner tasks, approval ids, created files, per-step token/cost estimates, and review results.


## LangChain / OpenAI

The `orchestrate_lc` endpoint now supports LangChain planning when `OPENAI_API_KEY` is configured.

```bash
curl -X POST http://localhost:8000/api/v1/agent/orchestrate_lc \
  -H "Content-Type: application/json" \
  -d '{"goal": "Create a URL shortener with analytics", "execute": false}'
```

If OpenAI is unavailable, the wrapper still falls back to the local orchestrator.


## Adding a Sample Admin Key

The repository already includes a sample `ADMIN_API_KEY` in `.env.example`:

```env
ADMIN_API_KEY=your_secret_key_here
```

Be sure to replace this value in your local `.env` file before using the app in production.

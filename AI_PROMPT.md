# AI Prompting Documentation

This file documents the high-value AI prompts used to implement and refine the URL shortener project.

## Worked Scenario 1: Greenfield
**Prompt:**
"Design the URL shortener from scratch. Build a FastAPI service that shortens URLs, stores them in SQLite, and supports redirecting short codes to the original URL. Include admin protection, analytics, observability, and Docker support."

**What I asked for:**
- Full application architecture from scratch.
- FastAPI backend, SQLAlchemy/SQLite persistence.
- URL shortening and redirect flow.
- Admin route protection, analytics, metrics, Docker.

**Why this worked:**
- It established the complete baseline app.
- It captured the project scope in one end-to-end prompt.
- It allowed the final implementation to include security, templates, and deployment support.

## Worked Scenario 2: Brownfield
**Prompt:**
"Add click analytics to the existing redirect endpoint and expose metrics. Keep the current redirect logic, add click counting and timestamps, and add admin analytics routes to view total clicks and unique visitors."

**Before:**
- Shorten and redirect endpoints existed.
- No analytics or click metrics were available.

**After:**
- Added click logging and click count updates.
- Added analytics routes for code stats and overall totals.
- Kept the existing redirect flow intact while extending functionality.

**Why this worked:**
- It incrementally improved the existing app instead of replacing it.
- It focused on a clear enhancement: analytics on redirect behavior.
- It preserved existing business logic and added observable features.

## Worked Scenario 3: Ambiguous
**Prompt:**
"Make it scalable. Ask how the app should behave under heavier traffic, whether link generation should be unique and collision-resistant, how the admin route should be protected, and what observability endpoints are required."

**What I interrogated:**
- How to handle slug collisions and uniqueness.
- Whether admin access should be gated by an API key.
- Whether SSRF protection was needed for submitted URLs.
- What metrics and telemetry matter for the service.

**Why this worked:**
- It exposed ambiguity in security, performance, and architecture.
- It led to design decisions around safe slug generation, admin auth, and observability.
- It ensured the final app matched real-world expectations rather than superficial requirements.

## Prompts I Rejected
1. **"Use a third-party URL shortening API instead of building your own."**
   - Rejected because the assignment requires building a self-contained service and avoiding external dependency for core functionality.

2. **"Accept any URL without validation and generate a slug."**
   - Rejected because it would introduce SSRF risk and allow unsafe redirects. The project needed host validation and private-address blocking.

3. **"Implement admin auth with a public login form and store credentials in plain text."**
   - Rejected because it is not technically secure. The app should use environment-managed API keys and minimal surface area for admin access.

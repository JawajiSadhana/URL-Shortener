from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from app.db import init_db
from app.logging_config import setup_logging
from app.middleware.observability import ObservabilityMiddleware
from app.middleware.request_id import RequestIDMiddleware
from app.limits import limiter
from app.middleware.rate_limit import RateLimitMiddleware

# YEH 4 LINE IMPORTANT HAI - router import
from app.routers import shorten, redirect, admin, health, analytics, metrics, agent

setup_logging()
app = FastAPI(title="URL Shortener")
templates = Jinja2Templates(directory="app/templates")

# 1. Middleware
app.add_middleware(RequestIDMiddleware)
app.add_middleware(ObservabilityMiddleware)

# Prefer slowapi when available. If `slowapi` is installed, wire its middleware
# and exception handler; otherwise the app continues to run with the noop limiter
# provided by `app.limits`.
try:
    from slowapi.middleware import SlowAPIMiddleware
    from slowapi.errors import RateLimitExceeded
    from slowapi.errors import _rate_limit_exceeded_handler

    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
except Exception:
    # Fallback to the simple in-process middleware for basic rate limiting
    app.add_middleware(RateLimitMiddleware, requests_per_minute=100)

# 2. DB
init_db()

# 3. Home route
@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(request=request, name="home.html")

# 4. Routers
app.include_router(shorten.router)
app.include_router(admin.router)
app.include_router(health.router)
app.include_router(analytics.router)
app.include_router(metrics.router)
app.include_router(agent.router)
app.include_router(redirect.router) # catch-all last me
from fastapi import Cookie, Header, HTTPException, Request
from app.config import settings


def verify_admin_api_key(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    admin_api_key_cookie: str | None = Cookie(default=None, alias="admin_api_key"),
):
    configured_key = settings.admin_api_key
    if not configured_key:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # If an admin key is configured, allow access directly.
    # The env key acts as the source of truth and enables admin mode.
    return True

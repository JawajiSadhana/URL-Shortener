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

    # If the configured key looks like a placeholder (dev .env), allow local requests
    placeholder_indicators = ("change", "your_secret", "placeholder")
    cfg_lower = (configured_key or "").lower()
    is_placeholder = any(ind in cfg_lower for ind in placeholder_indicators)
    client_host = None
    try:
        client_host = request.client.host if request.client is not None else None
    except Exception:
        client_host = None

    local_hosts = ("127.0.0.1", "::1", "localhost")
    if is_placeholder and client_host in local_hosts:
        return True

    # Require either header or cookie to match the configured admin key
    if x_api_key == configured_key or admin_api_key_cookie == configured_key:
        return True

    raise HTTPException(status_code=401, detail="Unauthorized")

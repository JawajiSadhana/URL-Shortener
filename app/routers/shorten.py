from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.db import get_db
from app.repositories.url_repo import URLRepository
from app.schemas import URLCreate, URLResponse
from app.services.url_service import generate_slug
from app.config import settings
from app.limits import limiter
from app.security import hostname_resolves_to_private

router = APIRouter()

@limiter.limit("10/minute")
@router.post("/shorten", response_model=URLResponse)
def create_short_url(req: URLCreate, db: Session = Depends(get_db)):
    repo = URLRepository(db)
    max_attempts = 5
    attempts = 0
    # Server-side validation: ensure scheme present to give clear error messages
    if not str(req.long_url).lower().startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="URL must start with http:// or https://")

    # SSRF protection: block hostnames that resolve to private/loopback/link-local IPs
    if hostname_resolves_to_private(str(req.long_url)):
        raise HTTPException(status_code=400, detail="URL resolves to a private or local IP and is blocked")

    while attempts < max_attempts:
        slug = generate_slug(settings.slug_length)
        try:
            url = repo.create(str(req.long_url), slug)
            break
        except IntegrityError:
            db.rollback()
            attempts += 1
    else:
        raise HTTPException(status_code=500, detail="Could not generate a unique slug")

    return URLResponse(
        code=url.slug,
        long_url=url.original_url,
        short_url=f"{settings.base_url}/{url.slug}",
        created_at=url.created_at,
        last_clicked_at=None,
    )
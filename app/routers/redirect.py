from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.repositories.url_repo import URLRepository
from app.db import get_db
from hashlib import sha256

router = APIRouter()

@router.get("/{code}")
def redirect_url(code: str, request: Request, db: Session = Depends(get_db)):
    repo = URLRepository(db)
    url = repo.get_by_code(code)
    if not url:
        raise HTTPException(status_code=404, detail="URL not found")

    referrer = request.headers.get("referer")
    user_agent = request.headers.get("user-agent")
    ip = request.client.host if request.client else "unknown"
    ip_hash = sha256(ip.encode("utf-8")).hexdigest()

    repo.update_last_clicked(code)
    repo.log_click(short_code=code, referrer=referrer, user_agent=user_agent, ip_hash=ip_hash)

    return RedirectResponse(url.original_url)
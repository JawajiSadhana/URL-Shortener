from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.repositories.url_repo import URLRepository
from app.db import get_db
from app.middleware.auth import verify_admin_api_key

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/admin")
def admin_panel(
    request: Request,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin_api_key),
):
    repo = URLRepository(db)
    urls = repo.get_all()
    return templates.TemplateResponse(request=request, name="admin.html", context={"urls": urls})

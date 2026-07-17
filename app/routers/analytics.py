from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app.services.analytics_service import AnalyticsService
from app.repositories.url_repo import URLRepository

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])

@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    service = AnalyticsService(db)
    return {
        "total_urls": service.get_total_urls(),
        "total_clicks": service.get_total_clicks()
    }

@router.get("/{code}")
def get_code_stats(code: str, db: Session = Depends(get_db)):
    repo = URLRepository(db)
    if not repo.get_by_code(code):
        raise HTTPException(status_code=404, detail="URL not found")

    service = AnalyticsService(db)
    return {
        "short_code": code,
        "total_clicks": service.get_total_clicks_for_code(code),
        "unique_visitors": service.get_unique_visitors(code),
    }
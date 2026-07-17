from sqlalchemy.orm import Session
from app import models
from datetime import datetime

class AnalyticsService:
    def __init__(self, db: Session):
        self.db = db

    def get_total_urls(self) -> int:
        """Total kitne short URLs bane"""
        return self.db.query(models.Url).count()

    def get_total_clicks(self) -> int:
        """Kitni baar redirect hua. Uses detailed click log."""
        return self.db.query(models.Click).count()

    def get_total_clicks_for_code(self, code: str) -> int:
        return self.db.query(models.Click).filter(models.Click.short_code == code).count()

    def get_unique_visitors(self, code: str) -> int:
        return self.db.query(models.Click.ip_hash).filter(models.Click.short_code == code).distinct().count()

    def get_top_urls(self, limit: int = 5):
        """Sabse zyada click wale top 5 URLs"""
        return self.db.query(models.Url)\
            .filter(models.Url.last_clicked_at.isnot(None))\
            .order_by(models.Url.last_clicked_at.desc())\
            .limit(limit).all()

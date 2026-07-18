from sqlalchemy.orm import Session
from app import models
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.exc import OperationalError, IntegrityError
import time


class URLRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(self):
        return self.db.query(models.Url).all()

    def get_by_slug(self, slug: str):
        # Return truthy if a row with this slug exists without loading full model
        row = self.db.query(models.Url.id).filter(models.Url.slug == slug).first()
        return bool(row)

    def get_by_code(self, code: str):
        return self.db.query(models.Url).filter(models.Url.slug == code).first()

    def _commit_with_retry(self, max_retries: int = 3, delay: float = 0.01):
        attempts = 0
        while True:
            try:
                self.db.commit()
                return
            except OperationalError:
                self.db.rollback()
                attempts += 1
                if attempts >= max_retries:
                    raise
                time.sleep(delay)

    def create(self, original_url: str, slug: str):
        # Do not store `short_url` in DB; compute it on read. Keep `code` for legacy admin views.
        # Prefer writing to `original_url` which exists in older DBs.
        db_url = models.Url(original_url=original_url, slug=slug, code=slug)
        self.db.add(db_url)
        try:
            self._commit_with_retry()
        except IntegrityError:
            # Let callers handle uniqueness collisions (they typically catch IntegrityError)
            raise

        # Reload the object from the DB to ensure it's persistent in this Session
        return self.db.query(models.Url).filter(models.Url.slug == slug).first()

    def update_last_clicked(self, code: str):
        # Use a direct UPDATE to ensure SQLite CURRENT_TIMESTAMP is applied
        try:
            self.db.execute(text("UPDATE urls SET clicks = COALESCE(clicks,0) + 1, last_clicked_at = CURRENT_TIMESTAMP WHERE slug = :code"), {"code": code})
            self._commit_with_retry()
        except Exception:
            self.db.rollback()

        return self.get_by_code(code)

    def log_click(self, short_code: str, referrer: str | None, user_agent: str | None, ip_hash: str | None):
        click = models.Click(
            short_code=short_code,
            referrer=referrer,
            user_agent=user_agent,
            ip_hash=ip_hash,
        )
        self.db.add(click)
        try:
            self._commit_with_retry()
        except Exception:
            self.db.rollback()
            raise
        self.db.refresh(click)
        return click

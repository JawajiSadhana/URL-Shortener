from sqlalchemy import Column, Integer, String, DateTime, Text, func
from app.db import Base
from app.config import settings


class Url(Base):
    __tablename__ = "urls"

    id = Column(Integer, primary_key=True, index=True)
    # Map both possible column names that may exist in older DBs.
    original_url = Column("original_url", String, nullable=True)
    long_url = Column("long_url", String, nullable=True)
    slug = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=func.now())
    clicks = Column(Integer, default=0)
    # Legacy optional columns
    code = Column("code", String(50))
    last_clicked_at = Column("last_clicked_at", DateTime)

    # Backwards-compatible accessor: prefer `original_url` then `long_url`.
    @property
    def resolved_original_url(self):
        return self.original_url or self.long_url

    # Compute short URL on read; do not persist duplicate short_url in DB
    @property
    def short_url(self):
        base = getattr(settings, "base_url", "http://localhost:8000")
        return f"{base.rstrip('/')}/{self.slug}"




class Click(Base):
    __tablename__ = "clicks"

    id = Column(Integer, primary_key=True, index=True)
    short_code = Column(String, nullable=False, index=True)
    clicked_at = Column(DateTime, default=func.now(), nullable=False)
    referrer = Column(Text)
    user_agent = Column(Text)
    ip_hash = Column(Text)

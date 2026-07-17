from pydantic import BaseModel, HttpUrl
from datetime import datetime
from typing import Optional

class URLCreate(BaseModel):
    long_url: HttpUrl

class URLResponse(BaseModel):
    code: str
    long_url: str
    short_url: str
    created_at: datetime
    last_clicked_at: Optional[datetime] = None

    class Config:
        from_attributes = True
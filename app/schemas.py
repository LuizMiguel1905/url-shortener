from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl

from app.config import settings
from app.models import Link


class LinkCreate(BaseModel):
    url: HttpUrl
    custom_code: str | None = Field(
        default=None, min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_-]+$"
    )


class LinkOut(BaseModel):
    code: str
    short_url: str
    target_url: str
    clicks: int
    created_at: datetime

    @classmethod
    def from_model(cls, link: Link) -> "LinkOut":
        return cls(
            code=link.code,
            short_url=f"{settings.base_url.rstrip('/')}/{link.code}",
            target_url=link.target_url,
            clicks=link.clicks,
            created_at=link.created_at,
        )

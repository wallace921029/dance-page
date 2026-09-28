from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class InviteCreate(BaseModel):
    valid_days: int = Field(default=7, ge=1, le=365)


class InviteUser(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str


class InviteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    # 不带分隔符的 8 位邀请码，前端显示为 K7M3-Q9TX
    code: str
    status: Literal["unused", "used", "expired", "revoked"]
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None
    used_at: datetime | None
    used_by: InviteUser | None

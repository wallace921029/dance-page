from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.auth.schemas import Password


class ReaderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    is_disabled: bool
    created_at: datetime
    # 最近使用时间（按天粗略记录）
    last_active_at: datetime | None


class ReaderUpdate(BaseModel):
    is_disabled: bool


class PasswordReset(BaseModel):
    password: Password

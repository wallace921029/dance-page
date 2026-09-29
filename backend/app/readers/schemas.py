from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from app.auth.schemas import Password


class ReaderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    # reader：读者；sub_admin：小小管理员（只有绘本模块的权限，D109）
    role: Literal["reader", "sub_admin"]
    is_disabled: bool
    created_at: datetime
    # 最近使用时间（按天粗略记录）
    last_active_at: datetime | None


class ReaderUpdate(BaseModel):
    """只修改请求中出现的字段。"""

    is_disabled: bool | None = None
    role: Literal["reader", "sub_admin"] | None = None

    @model_validator(mode="after")
    def _something_to_change(self) -> "ReaderUpdate":
        if self.is_disabled is None and self.role is None:
            raise ValueError("没有要修改的内容")
        return self


class PasswordReset(BaseModel):
    password: Password

import re
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict

from app.models import Role

USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_一-鿿]{2,20}$")
PASSWORD_MIN_LENGTH = 6
PASSWORD_MAX_LENGTH = 128


def _check_username(value: str) -> str:
    value = value.strip()
    if not USERNAME_PATTERN.fullmatch(value):
        raise ValueError("用户名需为 2–20 位中文、字母、数字或下划线")
    return value


def _check_password(value: str) -> str:
    if not PASSWORD_MIN_LENGTH <= len(value) <= PASSWORD_MAX_LENGTH:
        raise ValueError(f"密码至少 {PASSWORD_MIN_LENGTH} 位")
    return value


Username = Annotated[str, AfterValidator(_check_username)]
Password = Annotated[str, AfterValidator(_check_password)]


class LoginIn(BaseModel):
    # 登录时不校验格式，只要不对就统一提示"用户名或密码错误"
    username: str
    password: str


class RegisterIn(BaseModel):
    code: str
    username: Username
    password: Password


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: Role

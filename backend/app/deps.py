from typing import Annotated

from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.auth.sessions import SESSION_COOKIE, find_session, renew_if_due, set_session_cookie
from app.config import Settings
from app.db import get_db
from app.models import STAFF_ROLES, User

DbSession = Annotated[Session, Depends(get_db)]


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings


AppSettings = Annotated[Settings, Depends(get_app_settings)]


def get_current_user(
    request: Request, response: Response, db: DbSession, settings: AppSettings
) -> User | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    session = find_session(db, token)
    if session is None or session.user.is_disabled:
        return None
    if renew_if_due(session):
        db.commit()
        set_session_cookie(response, token, settings)
    return session.user


def require_user(user: Annotated[User | None, Depends(get_current_user)]) -> User:
    """任意已登录、未被禁用的用户（管理员也可以使用阅读端）。"""
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "请先登录")
    return user


def require_admin(user: Annotated[User, Depends(require_user)]) -> User:
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "需要管理员权限")
    return user


def require_staff(user: Annotated[User, Depends(require_user)]) -> User:
    """管理员或小小管理员：绘本模块（上传、编辑、AI 工作台）的权限（D109）。"""
    if user.role not in STAFF_ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "需要管理员权限")
    return user


CurrentUser = Annotated[User, Depends(require_user)]
# 仅管理员：用户管理、AI 配置
CurrentAdmin = Annotated[User, Depends(require_admin)]
# 管理员或小小管理员：绘本模块
CurrentStaff = Annotated[User, Depends(require_staff)]

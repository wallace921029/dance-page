import hashlib
import secrets
from datetime import timedelta

from fastapi import Response
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.clock import utcnow
from app.config import Settings
from app.models import User, UserSession

SESSION_COOKIE = "dp_session"
SESSION_TTL = timedelta(days=30)
# 距上次续期超过这个时间，就把过期时间顺延到 30 天后（避免每个请求都写数据库）
SESSION_RENEW_AFTER = timedelta(days=1)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(db: Session, user: User) -> str:
    """创建会话并返回明文令牌（只出现在 Cookie 里，数据库只存哈希）。"""
    token = secrets.token_urlsafe(32)
    now = utcnow()
    user.last_active_at = now
    db.add(
        UserSession(
            token_hash=_hash_token(token),
            user=user,
            created_at=now,
            last_seen_at=now,
            expires_at=now + SESSION_TTL,
        )
    )
    return token


def find_session(db: Session, token: str) -> UserSession | None:
    session = db.scalar(select(UserSession).where(UserSession.token_hash == _hash_token(token)))
    if session is None or session.expires_at <= utcnow():
        return None
    return session


def renew_if_due(session: UserSession) -> bool:
    now = utcnow()
    if now - session.last_seen_at < SESSION_RENEW_AFTER:
        return False
    session.last_seen_at = now
    session.expires_at = now + SESSION_TTL
    session.user.last_active_at = now
    return True


def delete_session(db: Session, token: str) -> None:
    db.execute(delete(UserSession).where(UserSession.token_hash == _hash_token(token)))


def delete_user_sessions(db: Session, user_id: int) -> None:
    db.execute(delete(UserSession).where(UserSession.user_id == user_id))


def set_session_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=int(SESSION_TTL.total_seconds()),
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )


def clear_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        SESSION_COOKIE, httponly=True, secure=settings.cookie_secure, samesite="lax"
    )

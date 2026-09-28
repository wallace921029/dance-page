from datetime import timedelta

from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.auth.passwords import hash_password, needs_rehash, verify_password
from app.auth.rate_limit import FailureLimiter
from app.auth.schemas import LoginIn, RegisterIn, UserOut
from app.auth.sessions import (
    SESSION_COOKIE,
    clear_session_cookie,
    create_session,
    delete_session,
    set_session_cookie,
)
from app.deps import AppSettings, CurrentUser, DbSession
from app.invites.service import claim_invite, find_usable_invite
from app.models import User

router = APIRouter(prefix="/auth", tags=["账户"])

LOGIN_LIMIT_WINDOW = timedelta(minutes=15)
LOGIN_MAX_FAILURES_PER_IP = 20
LOGIN_MAX_FAILURES_PER_USERNAME = 10
REGISTER_MAX_FAILURES_PER_IP = 10


def create_limiters() -> dict[str, FailureLimiter]:
    return {
        "login_ip": FailureLimiter(LOGIN_MAX_FAILURES_PER_IP, LOGIN_LIMIT_WINDOW),
        "login_username": FailureLimiter(LOGIN_MAX_FAILURES_PER_USERNAME, LOGIN_LIMIT_WINDOW),
        "register_ip": FailureLimiter(REGISTER_MAX_FAILURES_PER_IP, LOGIN_LIMIT_WINDOW),
    }


def _client_ip(request: Request) -> str:
    # 部署在 Nginx 后面时，uvicorn 的 --proxy-headers 会从 X-Forwarded-For 取真实 IP
    return request.client.host if request.client else "unknown"


@router.post("/login")
def login(
    body: LoginIn, request: Request, response: Response, db: DbSession, settings: AppSettings
) -> UserOut:
    limiters = request.app.state.limiters
    ip_key = _client_ip(request)
    username_key = body.username.strip().lower()
    limiters["login_ip"].check(ip_key)
    limiters["login_username"].check(username_key)

    user = db.scalar(select(User).where(User.username == body.username.strip()))
    password_ok = verify_password(user.password_hash if user else None, body.password)
    if user is None or not password_ok:
        limiters["login_ip"].record_failure(ip_key)
        limiters["login_username"].record_failure(username_key)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户名或密码错误")
    if user.is_disabled:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "该账号已被停用，请联系管理员")

    limiters["login_username"].reset(username_key)
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(body.password)
    token = create_session(db, user)
    db.commit()
    set_session_cookie(response, token, settings)
    return UserOut.model_validate(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: DbSession, settings: AppSettings) -> None:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        delete_session(db, token)
        db.commit()
    clear_session_cookie(response, settings)


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(
    body: RegisterIn, request: Request, response: Response, db: DbSession, settings: AppSettings
) -> UserOut:
    limiter: FailureLimiter = request.app.state.limiters["register_ip"]
    ip_key = _client_ip(request)
    limiter.check(ip_key)
    try:
        invite = find_usable_invite(db, body.code)
    except HTTPException:
        # 只有邀请码错误计入失败次数，防止暴力猜邀请码
        limiter.record_failure(ip_key)
        raise

    if db.scalar(select(User.id).where(User.username == body.username)) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "该用户名已被使用，请换一个")

    user = User(username=body.username, password_hash=hash_password(body.password), role="reader")
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "该用户名已被使用，请换一个") from None
    claim_invite(db, invite, user)
    token = create_session(db, user)
    db.commit()
    set_session_cookie(response, token, settings)
    return UserOut.model_validate(user)


@router.get("/me")
def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)

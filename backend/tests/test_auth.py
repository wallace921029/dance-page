from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.auth.sessions import SESSION_COOKIE
from app.config import Settings
from app.main import create_app
from app.models import User
from tests.conftest import ADMIN_PASSWORD, ADMIN_USERNAME, login


def test_admin_created_on_startup_and_can_login(client):
    user = login(client, ADMIN_USERNAME, ADMIN_PASSWORD)
    assert user["role"] == "admin"
    assert client.get("/api/auth/me").json() == user


def test_session_cookie_flags(client):
    res = client.post(
        "/api/auth/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD}
    )
    cookie = res.headers["set-cookie"]
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert "Max-Age=2592000" in cookie  # 30 天


def test_secure_cookie_by_default(settings):
    secure = settings.model_copy(update={"cookie_secure": True})
    with TestClient(create_app(secure), base_url="https://testserver") as c:
        res = c.post(
            "/api/auth/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD}
        )
    assert "Secure" in res.headers["set-cookie"]


def test_login_is_case_insensitive_for_username(client):
    assert login(client, "ADMIN", ADMIN_PASSWORD)["username"] == ADMIN_USERNAME


def test_wrong_password(client):
    res = client.post("/api/auth/login", json={"username": ADMIN_USERNAME, "password": "nope"})
    assert res.status_code == 401
    assert res.json() == {"detail": "用户名或密码错误"}


def test_unknown_user_gets_same_error(client):
    res = client.post("/api/auth/login", json={"username": "ghost", "password": "whatever"})
    assert res.status_code == 401
    assert res.json() == {"detail": "用户名或密码错误"}


def test_me_requires_login(client):
    res = client.get("/api/auth/me")
    assert res.status_code == 401
    assert res.json() == {"detail": "请先登录"}


def test_logout(client):
    login(client, ADMIN_USERNAME, ADMIN_PASSWORD)
    token = client.cookies[SESSION_COOKIE]
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").status_code == 401
    # 旧令牌在服务端也已失效
    client.cookies.set(SESSION_COOKIE, token)
    assert client.get("/api/auth/me").status_code == 401


def test_logout_without_session_is_ok(client):
    assert client.post("/api/auth/logout").status_code == 204


def test_login_rate_limited_per_username(client, advance):
    for _ in range(10):
        client.post("/api/auth/login", json={"username": ADMIN_USERNAME, "password": "bad"})
    res = client.post(
        "/api/auth/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD}
    )
    assert res.status_code == 429
    assert "分钟后再试" in res.json()["detail"]

    advance(timedelta(minutes=16))
    login(client, ADMIN_USERNAME, ADMIN_PASSWORD)


def test_login_rate_limited_per_ip(client):
    for i in range(20):
        client.post("/api/auth/login", json={"username": f"user{i}", "password": "bad"})
    res = client.post(
        "/api/auth/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD}
    )
    assert res.status_code == 429


def test_session_expires_after_30_days_without_use(admin, advance):
    advance(timedelta(days=30, minutes=1))
    assert admin.get("/api/auth/me").status_code == 401


def test_session_renewed_when_used(admin, advance):
    # 每隔 20 天用一次，累计超过 30 天仍保持登录
    for _ in range(3):
        advance(timedelta(days=20))
        res = admin.get("/api/auth/me")
        assert res.status_code == 200
        assert "Max-Age=2592000" in res.headers["set-cookie"]


def test_session_not_renewed_within_a_day(admin, advance):
    advance(timedelta(hours=12))
    res = admin.get("/api/auth/me")
    assert res.status_code == 200
    assert "set-cookie" not in res.headers


def test_admin_password_change_via_env(settings, new_client):
    # 首次启动时的会话
    old_device = new_client()
    login(old_device, ADMIN_USERNAME, ADMIN_PASSWORD)

    changed = settings.model_copy(update={"admin_password": "new-admin-pass"})
    with TestClient(create_app(changed)) as c:
        login(c, ADMIN_USERNAME, "new-admin-pass")
        res = c.post(
            "/api/auth/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD}
        )
        assert res.status_code == 401
    # 改密码后，之前登录的设备被登出
    assert old_device.get("/api/auth/me").status_code == 401


def test_admin_username_change_keeps_single_admin(settings, app):
    renamed = settings.model_copy(update={"admin_username": "boss"})
    renamed_app = create_app(renamed)
    with TestClient(renamed_app) as c:
        login(c, "boss", ADMIN_PASSWORD)
        with renamed_app.state.session_factory() as db:
            admins = db.scalars(select(User).where(User.role == "admin")).all()
    assert [a.username for a in admins] == ["boss"]


def test_admin_username_conflicting_with_reader_fails_startup(settings, reader):
    conflicting: Settings = settings.model_copy(update={"admin_username": "xiaoming"})
    with pytest.raises(RuntimeError, match="冲突"):
        with TestClient(create_app(conflicting)):
            pass


def test_validation_errors_are_chinese(client):
    res = client.post("/api/auth/login", json={"username": "admin"})
    assert res.status_code == 422
    assert res.json() == {"detail": "缺少必填项：password"}


def test_non_json_body_rejected(client):
    # 非 JSON 请求体（如跨站表单提交）不被接受
    res = client.post(
        "/api/auth/login",
        content=f"username={ADMIN_USERNAME}&password={ADMIN_PASSWORD}",
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert res.status_code == 422

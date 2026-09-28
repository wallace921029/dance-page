from collections.abc import Callable, Iterator
from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import clock
from app.config import Settings
from app.main import create_app

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin-pass"


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        admin_username=ADMIN_USERNAME,
        admin_password=ADMIN_PASSWORD,
        data_dir=tmp_path,
        cookie_secure=False,
        _env_file=None,
    )


@pytest.fixture
def app(settings) -> Iterator[FastAPI]:
    app = create_app(settings)
    # 进入 with 才会执行 lifespan（迁移 + 同步管理员）
    with TestClient(app):
        yield app


@pytest.fixture
def new_client(app) -> Callable[[], TestClient]:
    """每个客户端有独立的 Cookie，相当于一台独立的设备。"""
    return lambda: TestClient(app)


@pytest.fixture
def client(new_client) -> TestClient:
    return new_client()


@pytest.fixture
def admin(new_client) -> TestClient:
    c = new_client()
    login(c, ADMIN_USERNAME, ADMIN_PASSWORD)
    return c


@pytest.fixture
def advance() -> Iterator[Callable[[timedelta], None]]:
    """快进时间。"""

    def _advance(delta: timedelta) -> None:
        clock.offset += delta

    yield _advance
    clock.offset = timedelta(0)


def login(client: TestClient, username: str, password: str) -> dict:
    res = client.post("/api/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200, res.text
    return res.json()


def create_invite(admin: TestClient, **body) -> dict:
    res = admin.post("/api/admin/invites", json=body or None)
    assert res.status_code == 201, res.text
    return res.json()


def register(client: TestClient, code: str, username: str, password: str = "reader-pass"):
    return client.post(
        "/api/auth/register", json={"code": code, "username": username, "password": password}
    )


@pytest.fixture
def reader(admin, new_client) -> TestClient:
    """一个已注册并登录的读者（用户名 xiaoming）。"""
    c = new_client()
    res = register(c, create_invite(admin)["code"], "xiaoming")
    assert res.status_code == 201, res.text
    return c

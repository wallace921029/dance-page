from datetime import timedelta

from tests.conftest import ADMIN_PASSWORD, ADMIN_USERNAME, login


def _reader_id(admin) -> int:
    [reader] = admin.get("/api/admin/readers").json()
    return reader["id"]


def test_admin_endpoints_require_admin(client, reader):
    for method, path in [
        ("get", "/api/admin/invites"),
        ("post", "/api/admin/invites"),
        ("get", "/api/admin/readers"),
        ("post", "/api/admin/readers/1/reset-password"),
    ]:
        assert getattr(client, method)(path).status_code == 401, path
        res = getattr(reader, method)(path)
        assert res.status_code == 403, path
        assert res.json() == {"detail": "需要管理员权限"}


def test_list_readers(admin, reader):
    [listed] = admin.get("/api/admin/readers").json()
    assert listed["username"] == "xiaoming"
    assert listed["is_disabled"] is False
    assert listed["last_active_at"] is not None
    # 管理员不出现在读者列表中
    assert all(r["username"] != ADMIN_USERNAME for r in admin.get("/api/admin/readers").json())


def test_disable_reader_logs_out_immediately(admin, reader, new_client):
    reader_id = _reader_id(admin)
    res = admin.patch(f"/api/admin/readers/{reader_id}", json={"is_disabled": True})
    assert res.status_code == 200
    assert res.json()["is_disabled"] is True
    assert reader.get("/api/auth/me").status_code == 401

    res = new_client().post(
        "/api/auth/login", json={"username": "xiaoming", "password": "reader-pass"}
    )
    assert res.status_code == 403
    assert res.json() == {"detail": "该账号已被停用，请联系管理员"}

    admin.patch(f"/api/admin/readers/{reader_id}", json={"is_disabled": False})
    login(new_client(), "xiaoming", "reader-pass")


def test_reset_password(admin, reader, new_client):
    reader_id = _reader_id(admin)
    res = admin.post(
        f"/api/admin/readers/{reader_id}/reset-password", json={"password": "brand-new"}
    )
    assert res.status_code == 204
    # 旧设备被登出，旧密码失效
    assert reader.get("/api/auth/me").status_code == 401
    res = new_client().post(
        "/api/auth/login", json={"username": "xiaoming", "password": "reader-pass"}
    )
    assert res.status_code == 401
    login(new_client(), "xiaoming", "brand-new")


def test_reset_password_rules(admin, reader):
    res = admin.post(
        f"/api/admin/readers/{_reader_id(admin)}/reset-password", json={"password": "1"}
    )
    assert res.status_code == 422


def test_cannot_manage_admin_as_reader(admin):
    admin_id = admin.get("/api/auth/me").json()["id"]
    res = admin.patch(f"/api/admin/readers/{admin_id}", json={"is_disabled": True})
    assert res.status_code == 404
    login(admin, ADMIN_USERNAME, ADMIN_PASSWORD)


def test_last_active_updates_on_daily_use(admin, reader, advance):
    before = admin.get("/api/admin/readers").json()[0]["last_active_at"]
    advance(timedelta(days=2))
    reader.get("/api/auth/me")
    after = admin.get("/api/admin/readers").json()[0]["last_active_at"]
    assert after > before

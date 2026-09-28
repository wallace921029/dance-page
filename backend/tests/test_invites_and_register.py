from datetime import datetime, timedelta

from tests.conftest import create_invite, login, register


def test_create_invite_defaults_to_7_days(admin):
    invite = create_invite(admin)
    assert len(invite["code"]) == 8
    assert not set(invite["code"]) & set("01OIL")
    assert invite["status"] == "unused"
    assert invite["used_by"] is None
    created = datetime.fromisoformat(invite["created_at"])
    expires = datetime.fromisoformat(invite["expires_at"])
    assert expires - created == timedelta(days=7)


def test_create_invite_custom_days(admin):
    invite = create_invite(admin, valid_days=30)
    delta = datetime.fromisoformat(invite["expires_at"]) - datetime.fromisoformat(
        invite["created_at"]
    )
    assert delta == timedelta(days=30)


def test_invite_valid_days_range(admin):
    assert admin.post("/api/admin/invites", json={"valid_days": 0}).status_code == 422
    assert admin.post("/api/admin/invites", json={"valid_days": 366}).status_code == 422


def test_register_logs_in_and_marks_invite_used(admin, client):
    invite = create_invite(admin)
    res = register(client, invite["code"], "xiaoming")
    assert res.status_code == 201
    assert res.json()["role"] == "reader"
    assert client.get("/api/auth/me").json()["username"] == "xiaoming"

    [listed] = admin.get("/api/admin/invites").json()
    assert listed["status"] == "used"
    assert listed["used_by"]["username"] == "xiaoming"


def test_register_accepts_formatted_lowercase_code(admin, client):
    code = create_invite(admin)["code"]
    formatted = f" {code[:4].lower()}-{code[4:].lower()} "
    assert register(client, formatted, "xiaoming").status_code == 201


def test_register_with_chinese_username(admin, client):
    res = register(client, create_invite(admin)["code"], "小明_2")
    assert res.status_code == 201
    assert login(client, "小明_2", "reader-pass")["username"] == "小明_2"


def test_invite_is_single_use(admin, new_client):
    code = create_invite(admin)["code"]
    assert register(new_client(), code, "xiaoming").status_code == 201
    res = register(new_client(), code, "xiaohong")
    assert res.status_code == 400
    assert res.json() == {"detail": "该邀请码已被使用"}


def test_unknown_invite(client):
    res = register(client, "AAAA-BBBB", "xiaoming")
    assert res.status_code == 400
    assert "不存在" in res.json()["detail"]


def test_expired_invite(admin, client, advance):
    code = create_invite(admin, valid_days=1)["code"]
    advance(timedelta(days=1, seconds=1))
    res = register(client, code, "xiaoming")
    assert res.status_code == 400
    assert "过期" in res.json()["detail"]
    [listed] = admin.get("/api/admin/invites").json()
    assert listed["status"] == "expired"


def test_revoked_invite(admin, client):
    invite = create_invite(admin)
    res = admin.post(f"/api/admin/invites/{invite['id']}/revoke")
    assert res.status_code == 200
    assert res.json()["status"] == "revoked"
    res = register(client, invite["code"], "xiaoming")
    assert res.status_code == 400
    assert "作废" in res.json()["detail"]


def test_cannot_revoke_used_invite(admin, client):
    invite = create_invite(admin)
    register(client, invite["code"], "xiaoming")
    res = admin.post(f"/api/admin/invites/{invite['id']}/revoke")
    assert res.status_code == 409


def test_revoke_unknown_invite(admin):
    assert admin.post("/api/admin/invites/999/revoke").status_code == 404


def test_duplicate_username_case_insensitive(admin, new_client):
    assert register(new_client(), create_invite(admin)["code"], "XiaoMing").status_code == 201
    code = create_invite(admin)["code"]
    res = register(new_client(), code, "xiaoming")
    assert res.status_code == 409
    # 注册失败不消耗邀请码
    assert register(new_client(), code, "xiaohong").status_code == 201


def test_username_cannot_take_admin_name(admin, client):
    res = register(client, create_invite(admin)["code"], "Admin")
    assert res.status_code == 409


def test_username_and_password_rules(admin, client):
    code = create_invite(admin)["code"]
    res = register(client, code, "a")
    assert res.status_code == 422
    assert res.json() == {"detail": "用户名需为 2–20 位中文、字母、数字或下划线"}
    assert register(client, code, "has space").status_code == 422
    assert register(client, code, "x" * 21).status_code == 422
    res = register(client, code, "xiaoming", password="12345")
    assert res.status_code == 422
    assert res.json() == {"detail": "密码至少 6 位"}


def test_register_rate_limited_on_bad_codes(admin, client):
    for _ in range(10):
        register(client, "WRONGCODE", "xiaoming")
    res = register(client, create_invite(admin)["code"], "xiaoming")
    assert res.status_code == 429


def test_invite_list_newest_first(admin):
    first = create_invite(admin)
    second = create_invite(admin)
    assert [i["id"] for i in admin.get("/api/admin/invites").json()] == [second["id"], first["id"]]

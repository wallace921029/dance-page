"""小小管理员（D109）：管理员从读者里授予，只有"绘本"模块的权限，立即生效。"""

import pytest
from fastapi.testclient import TestClient

from tests.conftest import upload


@pytest.fixture
def reader_id(admin: TestClient, reader: TestClient) -> int:
    [row] = admin.get("/api/admin/readers").json()
    assert row["username"] == "xiaoming" and row["role"] == "reader"
    return row["id"]


def set_role(admin: TestClient, reader_id: int, role: str):
    return admin.patch(f"/api/admin/readers/{reader_id}", json={"role": role})


def test_promote_and_demote(admin, reader, reader_id):
    assert reader.get("/api/auth/me").json()["role"] == "reader"
    res = set_role(admin, reader_id, "sub_admin")
    assert res.status_code == 200 and res.json()["role"] == "sub_admin"
    # 权限按数据库里的角色实时判断，被授予的人不用重新登录
    assert reader.get("/api/auth/me").json()["role"] == "sub_admin"
    [row] = admin.get("/api/admin/readers").json()  # 仍在读者列表里，可以取消
    assert row["role"] == "sub_admin"

    res = set_role(admin, reader_id, "reader")
    assert res.status_code == 200 and res.json()["role"] == "reader"
    assert reader.get("/api/admin/books").status_code == 403


def test_sub_admin_can_manage_books(admin, reader, reader_id, worker, pdf_bytes):
    assert reader.get("/api/admin/books").status_code == 403  # 授权之前不行
    set_role(admin, reader_id, "sub_admin")

    assert reader.get("/api/admin/books").status_code == 200
    res = upload(reader, pdf_bytes)
    assert res.status_code == 201, res.text
    book = res.json()
    assert worker.run_once() is True
    detail = reader.get(f"/api/admin/books/{book['id']}")
    assert detail.status_code == 200
    # 绘本详情页里的 AI 工作台也属于绘本模块
    assert reader.get(f"/api/admin/books/{book['id']}/ai").status_code == 200
    res = reader.patch(f"/api/admin/books/{book['id']}", json={"title": "小小管理员改的书名"})
    assert res.status_code == 200 and res.json()["title"] == "小小管理员改的书名"
    assert reader.delete(f"/api/admin/books/{book['id']}").status_code == 204


def test_sub_admin_cannot_use_admin_only_modules(admin, reader, reader_id):
    set_role(admin, reader_id, "sub_admin")
    assert reader.get("/api/admin/invites").status_code == 403
    assert reader.post("/api/admin/invites").status_code == 403
    assert reader.get("/api/admin/readers").status_code == 403
    assert set_role(reader, reader_id, "reader").status_code == 403
    assert (
        reader.post(
            f"/api/admin/readers/{reader_id}/reset-password", json={"password": "another-pass"}
        ).status_code
        == 403
    )
    assert reader.get("/api/admin/ai/settings").status_code == 403
    config = {"provider": "dashscope", "model": "x", "base_url": "https://a.example", "options": {}}
    assert reader.put("/api/admin/ai/capabilities/video", json=config).status_code == 403
    # 授予不成功：角色没变
    assert admin.get("/api/admin/readers").json()[0]["role"] == "sub_admin"


def test_plain_reader_cannot_promote_anyone(admin, reader, reader_id):
    assert set_role(reader, reader_id, "sub_admin").status_code == 403
    assert admin.get("/api/admin/readers").json()[0]["role"] == "reader"


def test_sub_admin_previews_unlisted_books(admin, reader, reader_id, ready_book):
    admin.patch(f"/api/admin/books/{ready_book['id']}", json={"visibility": "unlisted"})
    assert reader.get(f"/api/books/{ready_book['id']}").status_code == 404
    set_role(admin, reader_id, "sub_admin")
    assert reader.get(f"/api/books/{ready_book['id']}").status_code == 200


def test_role_update_validation(admin, reader_id):
    assert admin.patch(f"/api/admin/readers/{reader_id}", json={}).status_code == 422
    assert admin.patch(f"/api/admin/readers/{reader_id}", json={"role": "admin"}).status_code == 422
    # 只改角色不影响停用状态，只改停用也不影响角色
    set_role(admin, reader_id, "sub_admin")
    res = admin.patch(f"/api/admin/readers/{reader_id}", json={"is_disabled": True})
    assert res.json()["role"] == "sub_admin" and res.json()["is_disabled"] is True
    res = set_role(admin, reader_id, "reader")
    assert res.json()["role"] == "reader" and res.json()["is_disabled"] is True


def test_admin_account_is_not_managed_as_reader(admin):
    [me] = [admin.get("/api/auth/me").json()]
    assert set_role(admin, me["id"], "reader").status_code == 404
    assert admin.get("/api/auth/me").json()["role"] == "admin"


def test_disabled_sub_admin_is_logged_out(admin, reader, reader_id):
    set_role(admin, reader_id, "sub_admin")
    admin.patch(f"/api/admin/readers/{reader_id}", json={"is_disabled": True})
    assert reader.get("/api/admin/books").status_code == 401

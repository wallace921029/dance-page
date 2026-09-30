import pytest
from sqlalchemy import select, update

from app.books import storage
from app.models import Job
from app.worker import runner
from tests.conftest import FILENAME, upload

# ---------- 上传与拆页 ----------


def test_upload_creates_processing_book(admin, settings, pdf_bytes):
    res = upload(admin, pdf_bytes)
    assert res.status_code == 201
    book = res.json()
    assert book["title"] == "波西和皮普 大怪兽"
    assert book["original_filename"] == FILENAME
    assert book["file_size"] == len(pdf_bytes)
    assert book["processing_status"] == "processing"
    assert book["progress"] == {"done": 0, "total": 0}
    assert book["visibility"] == "listed"
    assert book["cover_url"] is None
    assert storage.original_pdf_path(settings, book["id"]).read_bytes() == pdf_bytes


def test_worker_renders_book(admin, worker, settings, pdf_bytes):
    book_id = upload(admin, pdf_bytes).json()["id"]
    assert worker.run_once() is True
    assert worker.run_once() is False  # 队列已空

    book = admin.get(f"/api/admin/books/{book_id}").json()
    assert book["processing_status"] == "ready"
    assert book["progress"] is None
    assert book["page_count"] == 6
    assert book["orientation"] == "portrait"
    assert book["spread_start_detected"] == 3
    assert book["spread_start_page"] == 3
    assert book["cover_url"] == f"/api/books/{book_id}/cover?v=1"
    assert [p["index"] for p in book["pages"]] == list(range(6))
    # 裁掉底部白边后，页面比例接近画面本身（300×320）
    page = book["pages"][0]
    assert page["height"] == 2048
    assert page["width"] / page["height"] == pytest.approx(300 / 320, abs=0.01)
    assert storage.cover_path(settings, book_id).is_file()
    assert storage.page_path(settings, book_id, 5).is_file()


def test_upload_rejects_non_pdf(admin, settings):
    res = upload(admin, b"hello world", "notes.txt")
    assert res.status_code == 400
    assert res.json() == {"detail": "只支持 PDF 文件"}
    assert admin.get("/api/admin/books").json() == []
    assert not any((settings.data_dir / "books").glob("*"))


def test_upload_rejects_empty_file(admin):
    res = upload(admin, b"")
    assert res.status_code == 400


def test_upload_size_limit(admin, settings, monkeypatch):
    settings.max_upload_mb = 1
    # 明显超限的请求在进入接口前就被拦下（接口不会被调用）
    monkeypatch.setattr(storage, "original_pdf_path", lambda *_: pytest.fail("不应进入接口"))
    res = upload(admin, b"%PDF-" + b"0" * (3 * 1024 * 1024))
    assert res.status_code == 413
    assert res.json() == {"detail": "文件超过 1MB 上限"}
    assert admin.get("/api/admin/books").json() == []


def test_upload_size_limit_checked_while_copying(admin, settings):
    # 请求头里的长度没超（超出部分在预留的 1MB 开销内），复制时仍要按实际大小拦下
    settings.max_upload_mb = 1
    res = upload(admin, b"%PDF-" + b"0" * (1024 * 1024 + 100))
    assert res.status_code == 413
    assert not any((settings.data_dir / "books").glob("*"))


def test_corrupt_pdf_marks_book_failed(admin, worker):
    book_id = upload(admin, b"%PDF-1.4\nbroken").json()["id"]
    worker.run_once()
    book = admin.get(f"/api/admin/books/{book_id}").json()
    assert book["processing_status"] == "failed"
    assert "损坏" in book["processing_error"]
    assert book["progress"] is None


def test_upload_requires_admin(reader, client, pdf_bytes):
    assert upload(client, pdf_bytes).status_code == 401
    assert upload(reader, pdf_bytes).status_code == 403


def test_worker_recovers_interrupted_jobs(admin, worker, app, pdf_bytes):
    upload(admin, pdf_bytes)
    with app.state.session_factory() as db:
        db.execute(update(Job).values(status="running"))
        db.commit()
    assert worker.run_once() is False  # running 的任务不会被重复领取
    worker.recover()
    assert worker.run_once() is True


def test_worker_gives_up_render_killed_repeatedly(admin, worker, app, pdf_bytes):
    """拆页每次都把 Worker 杀掉（内存不足）：第一次中断后重试，第二次起标记失败并给出提示。"""
    book_id = upload(admin, pdf_bytes).json()["id"]

    def crash_while_running(attempts: int):
        with app.state.session_factory() as db:
            db.execute(update(Job).values(status="running", attempts=attempts))
            db.commit()
        worker.recover()

    crash_while_running(1)
    assert admin.get(f"/api/admin/books/{book_id}").json()["processing_status"] == "processing"

    crash_while_running(2)
    book = admin.get(f"/api/admin/books/{book_id}").json()
    assert book["processing_status"] == "failed"
    assert "内存不足" in book["processing_error"]
    assert worker.run_once() is False  # 不会再被领取


def test_book_deleted_while_processing(admin, worker, settings, pdf_bytes, monkeypatch):
    book_id = upload(admin, pdf_bytes).json()["id"]
    real_render = runner.render_pdf

    def render_then_delete(*args, **kwargs):
        # 模拟 Worker 开始处理后，管理员删除了这本书
        assert admin.delete(f"/api/admin/books/{book_id}").status_code == 204
        return real_render(*args, **kwargs)

    monkeypatch.setattr(runner, "render_pdf", render_then_delete)
    assert worker.run_once() is True
    assert not storage.book_dir(settings, book_id).exists()
    with worker.session_factory() as db:
        assert db.scalars(select(Job)).all() == []


# ---------- 编辑与删除 ----------


def test_update_book_info(admin, ready_book):
    book_id = ready_book["id"]
    res = admin.patch(
        f"/api/admin/books/{book_id}",
        json={
            "title": "  大怪兽  ",
            "language": "zh",
            "orientation": "landscape",
            "spread_start_override": 2,
            "visibility": "unlisted",
        },
    )
    assert res.status_code == 200
    book = res.json()
    assert book["title"] == "大怪兽"
    assert book["language"] == "zh"
    assert book["orientation"] == "landscape"
    assert book["spread_start_override"] == 2
    assert book["spread_start_page"] == 2
    assert book["visibility"] == "unlisted"

    # 传 null 清空：语言变回未设置，对开配对改回自动检测结果
    book = admin.patch(
        f"/api/admin/books/{book_id}", json={"language": None, "spread_start_override": None}
    ).json()
    assert book["language"] is None
    assert book["spread_start_page"] == 3
    # 未出现的字段不变
    assert book["title"] == "大怪兽"


def test_change_cover(admin, ready_book):
    book_id = ready_book["id"]
    book = admin.patch(f"/api/admin/books/{book_id}", json={"cover_page_index": 2}).json()
    assert book["cover_page_index"] == 2
    assert book["cover_url"] == f"/api/books/{book_id}/cover?v=2"
    assert book["pages"][0]["url"].endswith("?v=2")

    res = admin.patch(f"/api/admin/books/{book_id}", json={"cover_page_index": 6})
    assert res.status_code == 400


def test_cannot_change_cover_while_processing(admin, pdf_bytes):
    book_id = upload(admin, pdf_bytes).json()["id"]
    res = admin.patch(f"/api/admin/books/{book_id}", json={"cover_page_index": 1})
    assert res.status_code == 409


def test_update_validation(admin, ready_book):
    url = f"/api/admin/books/{ready_book['id']}"
    res = admin.patch(url, json={"title": "   "})
    assert res.status_code == 422
    assert res.json() == {"detail": "书名需为 1–100 个字"}
    assert admin.patch(url, json={"spread_start_override": 4}).status_code == 422
    assert admin.patch(url, json={"language": "fr"}).status_code == 422


def test_delete_book(admin, reader, ready_book, settings):
    book_id = ready_book["id"]
    assert admin.delete(f"/api/admin/books/{book_id}").status_code == 204
    assert not storage.book_dir(settings, book_id).exists()
    assert admin.get(f"/api/admin/books/{book_id}").status_code == 404
    assert reader.get("/api/books").json() == []


def test_admin_list_newest_first(admin, pdf_bytes):
    first = upload(admin, pdf_bytes, "a.pdf").json()
    second = upload(admin, pdf_bytes, "b.pdf").json()
    assert [b["id"] for b in admin.get("/api/admin/books").json()] == [second["id"], first["id"]]


def test_admin_list_search(admin, pdf_bytes):
    book_a = upload(admin, pdf_bytes, "大怪兽.pdf").json()
    book_b = upload(admin, pdf_bytes, "小怪兽.pdf").json()
    book_c = upload(admin, pdf_bytes, "红苹果.pdf").json()

    # 搜书名
    res = admin.get("/api/admin/books?q=怪兽").json()
    assert [b["id"] for b in res] == [book_b["id"], book_a["id"]]

    # 搜不存在的
    res = admin.get("/api/admin/books?q=香蕉").json()
    assert res == []

    # 搜原文件名
    res = admin.get("/api/admin/books?q=红苹果.pdf").json()
    assert [b["id"] for b in res] == [book_c["id"]]


# ---------- 阅读端 ----------


def test_shelf_shows_only_listed_ready_books(admin, reader, worker, ready_book, pdf_bytes):
    upload(admin, pdf_bytes, "processing.pdf")  # 还没处理
    shelf = reader.get("/api/books").json()
    assert [b["id"] for b in shelf] == [ready_book["id"]]
    assert shelf[0]["cover_url"] == ready_book["cover_url"]

    admin.patch(f"/api/admin/books/{ready_book['id']}", json={"visibility": "unlisted"})
    assert reader.get("/api/books").json() == []


def test_reader_book_detail(reader, ready_book):
    res = reader.get(f"/api/books/{ready_book['id']}")
    assert res.status_code == 200
    book = res.json()
    assert book["spread_start_page"] == 3
    assert len(book["pages"]) == 6
    assert book["pages"][0]["url"] == ready_book["pages"][0]["url"]
    assert "processing_status" not in book


def test_page_and_cover_images(reader, ready_book):
    page = reader.get(ready_book["pages"][1]["url"])
    assert page.status_code == 200
    assert page.headers["content-type"] == "image/webp"
    assert "immutable" in page.headers["cache-control"]
    assert reader.get(ready_book["cover_url"]).status_code == 200
    assert reader.get(f"/api/books/{ready_book['id']}/pages/6").status_code == 404


def test_images_require_login(client, ready_book):
    assert client.get(ready_book["cover_url"]).status_code == 401
    assert client.get(ready_book["pages"][0]["url"]).status_code == 401
    assert client.get("/api/books").status_code == 401


def test_unlisted_book_hidden_from_reader_but_admin_can_preview(admin, reader, ready_book):
    book_id = ready_book["id"]
    admin.patch(f"/api/admin/books/{book_id}", json={"visibility": "unlisted"})
    assert reader.get(f"/api/books/{book_id}").status_code == 404
    assert reader.get(ready_book["pages"][0]["url"]).status_code == 404
    assert admin.get(f"/api/books/{book_id}").status_code == 200
    assert admin.get(ready_book["pages"][0]["url"]).status_code == 200

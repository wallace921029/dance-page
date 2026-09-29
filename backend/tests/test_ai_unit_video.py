"""开页动画（A4）：单元首尾帧视频、合并开页拼图、全部生成、Dance Ready! 与阅读端。"""

import io
import json

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.ai import providers
from app.books import storage
from app.models import Job
from tests.test_ai_cover_video import POLL, FakeWan

# 测试书：封面(0)、第 1 页单独、2+3、4+5 两个对开
ANALYSIS = {
    "story": "小熊和兔子去野餐。",
    "characters": [{"name": "旁白", "is_narrator": True, "voice_prompt": "温柔女声"}],
    "pages": [
        {"page_index": 0, "lines": [], "motion_prompt": "小熊眨眨眼"},
        {"page_index": 1, "lines": [], "motion_prompt": ""},
        {"page_index": 2, "lines": [], "motion_prompt": "小熊挥挥手。"},
        {"page_index": 3, "lines": [], "motion_prompt": "兔子的耳朵抖一抖"},
        {"page_index": 4, "lines": [], "motion_prompt": "风筝在天上轻轻摆动"},
        {"page_index": 5, "lines": [], "motion_prompt": "小熊拉着线点点头"},
    ],
    "spread_suggestions": [
        {"pages": [2, 3], "is_same_scene": False},
        {"pages": [4, 5], "is_same_scene": True},
    ],
}


@pytest.fixture
def wan(monkeypatch, app) -> FakeWan:
    app.state.settings.dashscope_api_key = "sk-test-key"
    fake = FakeWan()
    monkeypatch.setattr(
        providers, "http_client", lambda: httpx.Client(transport=httpx.MockTransport(fake.handler))
    )
    return fake


@pytest.fixture
def analyzed(admin: TestClient, worker, ready_book: dict, wan: FakeWan) -> dict:
    wan.analysis = ANALYSIS
    admin.post(f"/api/admin/books/{ready_book['id']}/ai/analyze")
    assert worker.run_once() is True
    return ready_book


def book_ai(admin: TestClient, book_id: str) -> dict:
    return admin.get(f"/api/admin/books/{book_id}/ai").json()


def unit_at(admin: TestClient, book_id: str, page: int) -> dict:
    units = [u for s in book_ai(admin, book_id)["spreads"] for u in s["units"]]
    return next(u for u in units if u["first_page_index"] == page)


def run_jobs(worker, advance) -> None:
    """跑完所有任务：提交、等待查询（假服务商先 RUNNING 再 SUCCEEDED）、下载。"""
    for _ in range(20):
        while worker.run_once():
            pass
        advance(POLL)
    assert worker.run_once() is False


def generate(admin: TestClient, unit: dict, **body):
    return admin.post(f"/api/admin/ai/units/{unit['id']}/video", json=body or None)


def uploaded_frames(wan: FakeWan) -> list[Image.Image]:
    """上传到服务商临时存储的首帧图片。"""
    frames = []
    for r in wan.requests:
        if str(r.url) == "https://oss.example.com":
            start = r.content.index(b"\xff\xd8")
            frames.append(Image.open(io.BytesIO(r.content[start:])))
    return frames


def test_analysis_drafts(admin, analyzed):
    book_id = analyzed["id"]
    ai = book_ai(admin, book_id)
    assert ai["video_options"] == {
        "durations": [5],
        "resolutions": ["480P", "720P", "1080P"],
        "default_duration": 5,
        "default_resolution": "480P",
    }
    # 没有可动内容的页面：动作描述为空，不生成动画
    assert unit_at(admin, book_id, 1)["motion_prompt"] is None
    # 第 1 页是封面：由封面动画负责
    assert unit_at(admin, book_id, 0)["video_by_cover"] is True
    assert unit_at(admin, book_id, 2)["video_by_cover"] is False
    merged = unit_at(admin, book_id, 4)
    assert merged["page_count"] == 2
    assert merged["motion_prompt"] == "风筝在天上轻轻摆动；小熊拉着线点点头"


def test_unit_video_flow(admin, reader, worker, advance, analyzed, wan):
    book_id = analyzed["id"]
    unit = unit_at(admin, book_id, 2)
    assert unit["video_status"] == "none" and unit["video_url"] is None

    res = generate(admin, unit)
    assert res.status_code == 202, res.text
    assert generate(admin, unit).json()["job_id"] == res.json()["job_id"]  # 不重复排队
    assert unit_at(admin, book_id, 2)["video_status"] == "queued"

    assert worker.run_once() is True  # 提交
    (submit,) = wan.submits()
    body = json.loads(submit.content)
    assert body["input"]["img_url"] == "oss://dashscope-instant/abc/frame.jpg"
    # 句末的句号去掉后接进模板
    assert "小熊挥挥手。主体的动作清楚、明显" in body["input"]["prompt"]
    assert "文字完全不变" in body["input"]["prompt"]
    assert "画面静止不动" in body["input"]["negative_prompt"]
    assert body["parameters"] == {"resolution": "480P", "prompt_extend": True}
    # 等待查询期间照常轮询
    jobs = book_ai(admin, book_id)["running_jobs"]
    assert [(j["type"], j["status"]) for j in jobs] == [("ai_video_unit", "waiting")]
    assert unit_at(admin, book_id, 2)["video_status"] == "running"

    run_jobs(worker, advance)
    done = unit_at(admin, book_id, 2)
    assert done["video_status"] == "ready"
    assert done["video_error"] is None
    assert done["video_duration_s"] == 5 and done["video_resolution"] == "480P"
    assert done["video_outdated"] is False
    assert done["video_url"] == f"/api/admin/ai/units/{unit['id']}/video?v=1"
    res = admin.get(done["video_url"])
    assert res.status_code == 200 and res.headers["content-type"] == "video/mp4"
    assert reader.get(done["video_url"]).status_code == 403

    # 确认 Dance Ready! 之前读者看不到
    reader_video = f"/api/books/{book_id}/ai/video/{unit['id']}"
    detail = reader.get(f"/api/books/{book_id}").json()
    assert detail["units"] == [] and detail["dance_ready"] is False
    assert reader.get(reader_video).status_code == 404

    res = admin.put(f"/api/admin/books/{book_id}/ai/dance-ready")
    assert res.status_code == 200 and res.json()["dance_ready_at"] is not None
    detail = reader.get(f"/api/books/{book_id}").json()
    assert detail["dance_ready"] is True
    assert detail["units"] == [
        {
            "pages": [2],
            "audio_url": None,
            "audio_duration_ms": None,
            "video_url": f"{reader_video}?v=1",
        }
    ]
    shelf = next(b for b in reader.get("/api/books").json() if b["id"] == book_id)
    assert shelf["dance_ready"] is True and shelf["voice_ready"] is False
    res = reader.get(reader_video, headers={"Range": "bytes=0-99"})
    assert res.status_code == 206 and len(res.content) == 100

    # 改了动作描述：需要重新生成，读者仍看到旧的
    admin.patch(f"/api/admin/ai/units/{unit['id']}", json={"motion_prompt": "小熊跳一跳"})
    assert unit_at(admin, book_id, 2)["video_outdated"] is True
    assert reader.get(reader_video).status_code == 200

    # 关闭开页动画：读者看不到
    admin.patch(f"/api/admin/books/{book_id}/ai/spreads/2", json={"video_enabled": False})
    assert reader.get(f"/api/books/{book_id}").json()["units"] == []
    assert reader.get(reader_video).status_code == 404
    admin.patch(f"/api/admin/books/{book_id}/ai/spreads/2", json={"video_enabled": True})

    admin.delete(f"/api/admin/books/{book_id}/ai/dance-ready")
    assert reader.get(f"/api/books/{book_id}").json()["units"] == []


def test_merged_unit_uses_stitched_frame(admin, worker, advance, analyzed, wan):
    book_id = analyzed["id"]
    assert generate(admin, unit_at(admin, book_id, 2)).status_code == 202
    assert generate(admin, unit_at(admin, book_id, 4)).status_code == 202
    worker.run_once()
    worker.run_once()
    single, merged = uploaded_frames(wan)
    # 合并开页：左右两页拼成一张整图，宽高比是单页的两倍
    assert merged.width / merged.height == pytest.approx(2 * single.width / single.height, rel=0.02)
    prompt = json.loads(wan.submits()[1].content)["input"]["prompt"]
    assert "风筝在天上轻轻摆动；小熊拉着线点点头" in prompt


def test_cannot_generate(admin, analyzed, wan):
    book_id = analyzed["id"]
    res = generate(admin, unit_at(admin, book_id, 0))
    assert res.status_code == 400 and "封面动画" in res.json()["detail"]
    res = generate(admin, unit_at(admin, book_id, 1))
    assert res.status_code == 400 and "动作描述" in res.json()["detail"]

    unit = unit_at(admin, book_id, 2)
    res = generate(admin, unit, resolution="1440P")
    assert res.status_code == 400 and "清晰度" in res.json()["detail"]
    res = generate(admin, unit, duration=10)
    assert res.status_code == 400 and "5 秒" in res.json()["detail"]

    admin.patch(f"/api/admin/books/{book_id}/ai/spreads/2", json={"video_enabled": False})
    res = generate(admin, unit)
    assert res.status_code == 400 and "关闭动画" in res.json()["detail"]
    res = admin.post(f"/api/admin/books/{book_id}/ai/spreads/2/video")
    assert res.status_code == 400 and "关闭动画" in res.json()["detail"]

    res = admin.put(f"/api/admin/books/{book_id}/ai/dance-ready")
    assert res.status_code == 400 and "还没有生成任何动画" in res.json()["detail"]


def test_temporary_resolution(admin, worker, advance, analyzed, wan):
    """生成时临时换清晰度（D79）：只影响这一次，不算"需要重新生成"。"""
    book_id = analyzed["id"]
    assert generate(admin, unit_at(admin, book_id, 2), resolution="480P").status_code == 202
    run_jobs(worker, advance)
    assert json.loads(wan.submits()[0].content)["parameters"]["resolution"] == "480P"
    done = unit_at(admin, book_id, 2)
    assert done["video_resolution"] == "480P"
    assert done["video_outdated"] is False
    # 全部生成：已是最新的不再生成
    res = admin.post(f"/api/admin/books/{book_id}/ai/generate-all?type=video")
    assert res.json() == {"queued": 2}  # 第 3 页和合并的 4+5


def test_generate_all_and_spread(admin, worker, advance, analyzed, wan):
    book_id = analyzed["id"]
    url = f"/api/admin/books/{book_id}/ai/generate-all?type=video"
    # 跳过封面页（0）和没有动作描述的第 1 页
    assert admin.post(url).json() == {"queued": 3}
    assert admin.post(url).json() == {"queued": 0}  # 已在队列里
    run_jobs(worker, advance)
    for page in (2, 3, 4):
        assert unit_at(admin, book_id, page)["video_status"] == "ready"
    assert admin.post(url).json() == {"queued": 0}

    admin.patch(
        f"/api/admin/ai/units/{unit_at(admin, book_id, 3)['id']}",
        json={"motion_prompt": "兔子蹦一下"},
    )
    assert admin.post(url).json() == {"queued": 1}
    run_jobs(worker, advance)

    # 生成本开页动画：不管是否最新，开页里的单元都重新生成
    res = admin.post(f"/api/admin/books/{book_id}/ai/spreads/2/video")
    assert res.status_code == 202 and res.json() == {"queued": 2}
    run_jobs(worker, advance)
    assert unit_at(admin, book_id, 2)["video_url"].endswith("?v=2")


def test_switch_off_cancels_queued(admin, worker, analyzed, wan):
    book_id = analyzed["id"]
    admin.post(f"/api/admin/books/{book_id}/ai/spreads/2/video")
    admin.patch(f"/api/admin/books/{book_id}/ai/spreads/2", json={"video_enabled": False})
    assert unit_at(admin, book_id, 2)["video_status"] == "none"
    assert book_ai(admin, book_id)["running_jobs"] == []
    assert worker.run_once() is False
    assert wan.submits() == []


def test_mode_change_discards_result(admin, app, settings, worker, advance, analyzed, wan):
    """查询期间开页改成了分别生成：结果对不上这个单元，作废（不覆盖成错误的画面）。"""
    book_id = analyzed["id"]
    unit = unit_at(admin, book_id, 4)
    generate(admin, unit)
    worker.run_once()
    admin.put(f"/api/admin/books/{book_id}/ai/spreads/4", json={"mode": "separate"})
    run_jobs(worker, advance)
    after = unit_at(admin, book_id, 4)
    assert after["page_count"] == 1
    assert after["video_status"] == "none" and after["video_url"] is None
    assert not storage.ai_video_path(settings, book_id, unit["id"]).exists()
    with app.state.session_factory() as db:
        job = db.query(Job).filter(Job.type == "ai_video_unit").one()
        assert job.status == "failed" and "作废" in job.error


def test_provider_failure_keeps_old_video(admin, worker, advance, analyzed, wan):
    book_id = analyzed["id"]
    unit = unit_at(admin, book_id, 2)
    generate(admin, unit)
    run_jobs(worker, advance)
    wan.poll_statuses = ["FAILED"]
    generate(admin, unit)
    run_jobs(worker, advance)
    failed = unit_at(admin, book_id, 2)
    assert failed["video_status"] == "failed"
    assert "图片未通过审核" in failed["video_error"]
    # 上一版仍可预览，也能确认 Dance Ready!
    assert admin.get(failed["video_url"]).status_code == 200
    assert admin.put(f"/api/admin/books/{book_id}/ai/dance-ready").status_code == 200


ARK = "https://ark.cn-beijing.volces.com/api/v3"


def test_volcengine_seedance(admin, app, monkeypatch, worker, advance, analyzed):
    """火山 Seedance 图生视频（D99）：首帧以 base64 传，画面比例跟随首帧，查询后下载。"""
    from tests.test_ai_cover_video import RESULT_MP4

    book_id = analyzed["id"]
    app.state.settings.volcengine_ark_api_key = "ark-test-key"
    res = admin.put(
        "/api/admin/ai/capabilities/video",
        json={
            "provider": "volcengine",
            "model": "doubao-seedance-2-0-fast-260128",
            "base_url": ARK,
            "options": {"duration": 5, "resolution": "720p"},
        },
    )
    assert res.status_code == 200, res.text
    requests: list[httpx.Request] = []
    statuses = ["running", "succeeded"]

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        url = str(request.url)
        if url == f"{ARK}/contents/generations/tasks":
            return httpx.Response(200, json={"id": "cgt-1"})
        if url == f"{ARK}/contents/generations/tasks/cgt-1":
            status = statuses.pop(0) if len(statuses) > 1 else statuses[0]
            body: dict = {"id": "cgt-1", "status": status}
            if status == "succeeded":
                body["content"] = {"video_url": "https://tos.example.com/v.mp4"}
            return httpx.Response(200, json=body)
        if url == "https://tos.example.com/v.mp4":
            return httpx.Response(200, content=RESULT_MP4)
        return httpx.Response(404)

    monkeypatch.setattr(
        providers, "http_client", lambda: httpx.Client(transport=httpx.MockTransport(handler))
    )
    unit = unit_at(admin, book_id, 2)
    assert generate(admin, unit).status_code == 202
    run_jobs(worker, advance)

    submit = next(r for r in requests if r.method == "POST")
    assert submit.headers["Authorization"] == "Bearer ark-test-key"
    body = json.loads(submit.content)
    assert body["model"] == "doubao-seedance-2-0-fast-260128"
    text, image = body["content"]
    assert text["type"] == "text" and "小熊挥挥手" in text["text"]
    assert image["role"] == "first_frame"
    assert image["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert (body["ratio"], body["resolution"], body["duration"]) == ("adaptive", "720p", 5)
    done = unit_at(admin, book_id, 2)
    assert done["video_status"] == "ready" and done["video_resolution"] == "720p"


def test_volcengine_failure_message(admin, app, monkeypatch, worker, advance, analyzed):
    book_id = analyzed["id"]
    app.state.settings.volcengine_ark_api_key = "ark-test-key"
    admin.put(
        "/api/admin/ai/capabilities/video",
        json={
            "provider": "volcengine",
            "model": "doubao-seedance-x",
            "base_url": ARK,
            "options": {},
        },
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(200, json={"id": "cgt-2"})
        return httpx.Response(
            200, json={"id": "cgt-2", "status": "failed", "error": {"message": "内容审核未通过"}}
        )

    monkeypatch.setattr(
        providers, "http_client", lambda: httpx.Client(transport=httpx.MockTransport(handler))
    )
    generate(admin, unit_at(admin, book_id, 2))
    run_jobs(worker, advance)
    failed = unit_at(admin, book_id, 2)
    assert failed["video_status"] == "failed"
    assert failed["video_error"] == "服务商返回：内容审核未通过"


def test_seedance_options_and_stale_saved_duration(admin, app, monkeypatch, worker, analyzed):
    """Seedance 2.0 只接受 4–15 秒；之前按猜测范围保存的 3 秒不再发出去，改用该模型的默认值。"""
    from app.models import AiCapabilityConfig

    book_id = analyzed["id"]
    app.state.settings.volcengine_ark_api_key = "ark-test-key"
    admin.put(
        "/api/admin/ai/capabilities/video",
        json={
            "provider": "volcengine",
            "model": "doubao-seedance-2-0-260128",
            "base_url": ARK,
            "options": {},
        },
    )
    # 模拟修正可选范围之前保存的设置
    with app.state.session_factory() as db:
        row = db.get(AiCapabilityConfig, ("video", "volcengine"))
        row.options = {"duration": 3, "resolution": "720p"}
        db.commit()

    options = book_ai(admin, book_id)["video_options"]
    assert options["durations"] == [4, 5, 6, 8, 10, 12, 15]
    assert options["resolutions"] == ["480p", "720p", "1080p"]
    assert (options["default_duration"], options["default_resolution"]) == (5, "720p")
    res = admin.put(
        "/api/admin/ai/capabilities/video",
        json={
            "provider": "volcengine",
            "model": "doubao-seedance-2-0-fast-260128",
            "base_url": ARK,
            "options": {"duration": 3},
        },
    )
    assert res.status_code == 422 and "4 秒" in res.json()["detail"]
    fast = admin.put(
        "/api/admin/ai/capabilities/video",
        json={
            "provider": "volcengine",
            "model": "doubao-seedance-2-0-fast-260128",
            "base_url": ARK,
            "options": {"duration": 8, "resolution": "720p"},
        },
    )
    assert fast.status_code == 200, fast.text
    assert book_ai(admin, book_id)["video_options"]["resolutions"] == ["480p", "720p"]

    with app.state.session_factory() as db:
        row = db.get(AiCapabilityConfig, ("video", "volcengine"))
        row.options = {"duration": 3, "resolution": "1080p"}  # Fast 不支持
        db.commit()
    submitted: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            submitted.append(json.loads(request.content))
            return httpx.Response(200, json={"id": "cgt-3"})
        return httpx.Response(200, json={"id": "cgt-3", "status": "running"})

    monkeypatch.setattr(
        providers, "http_client", lambda: httpx.Client(transport=httpx.MockTransport(handler))
    )
    generate(admin, unit_at(admin, book_id, 2))
    worker.run_once()
    assert (submitted[0]["duration"], submitted[0]["resolution"]) == (5, "480p")

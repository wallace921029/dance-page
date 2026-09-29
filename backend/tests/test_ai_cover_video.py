"""封面动画（D96、D99）：上传首帧、提交图生视频任务、定时查询、下载后做成来回循环、启用后读者可见。"""

import io
import json
from datetime import timedelta

import av
import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.ai import providers
from app.books import storage
from app.models import Job
from app.worker.runner import MAX_REMOTE_VIDEOS, VIDEO_MAX_WAIT

API = "https://dashscope.aliyuncs.com/api/v1"
SUBMIT_URL = f"{API}/services/aigc/video-generation/video-synthesis"
# 首尾帧模型（kf2v）的提交地址
KEYFRAMES_URL = f"{API}/services/aigc/image2video/video-synthesis"
POLL = timedelta(seconds=16)


def make_mp4() -> bytes:
    """一段带音轨的小视频，模拟服务商的生成结果。"""
    buf = io.BytesIO()
    with av.open(buf, mode="w", format="mp4") as out:
        video = out.add_stream("libx264", rate=24)
        video.width, video.height, video.pix_fmt = 64, 48, "yuv420p"
        sound = out.add_stream("aac", rate=24000, layout="mono")
        for i in range(24):
            frame = av.VideoFrame.from_ndarray(
                np.full((48, 64, 3), i * 8, dtype=np.uint8), format="rgb24"
            )
            for packet in video.encode(frame):
                out.mux(packet)
        for packet in video.encode():
            out.mux(packet)
        silence = av.AudioFrame.from_ndarray(
            np.zeros((1, 24000), dtype=np.int16), format="s16", layout="mono"
        )
        silence.rate, silence.pts = 24000, 0
        for packet in sound.encode(silence):
            out.mux(packet)
        for packet in sound.encode(None):
            out.mux(packet)
    return buf.getvalue()


RESULT_MP4 = make_mp4()


class FakeWan:
    """假的百炼：上传凭证、OSS 直传、提交视频任务、查询（先 RUNNING 再给出结果）、下载。"""

    def __init__(self):
        self.requests: list[httpx.Request] = []
        self.poll_statuses = ["RUNNING", "SUCCEEDED"]
        self.poll_error: httpx.Response | None = None
        # 视觉模型的回答：看封面写动作描述，或分析整本故事
        self.analysis: dict | None = {"motion": "兔子眨眨眼，小老鼠的尾巴轻轻摆动"}

    def submits(self) -> list[httpx.Request]:
        return [r for r in self.requests if str(r.url) in (SUBMIT_URL, KEYFRAMES_URL)]

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        url = str(request.url)
        if request.url.path.endswith("/chat/completions"):
            content = json.dumps(self.analysis, ensure_ascii=False)
            return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})
        if url.startswith(f"{API}/uploads"):
            return httpx.Response(
                200,
                json={
                    "data": {
                        "policy": "p",
                        "signature": "s",
                        "upload_dir": "dashscope-instant/abc",
                        "upload_host": "https://oss.example.com",
                        "oss_access_key_id": "id",
                        "x_oss_object_acl": "private",
                        "x_oss_forbid_overwrite": "true",
                    }
                },
            )
        if url == "https://oss.example.com":
            return httpx.Response(200)
        if url in (SUBMIT_URL, KEYFRAMES_URL):
            return httpx.Response(
                200, json={"output": {"task_id": "task-1", "task_status": "PENDING"}}
            )
        if url == f"{API}/tasks/task-1":
            if self.poll_error is not None:
                return self.poll_error
            status = (
                self.poll_statuses.pop(0) if len(self.poll_statuses) > 1 else self.poll_statuses[0]
            )
            output: dict = {"task_id": "task-1", "task_status": status}
            if status == "SUCCEEDED":
                output["video_url"] = "https://oss.example.com/result.mp4"
            if status == "FAILED":
                output["code"], output["message"] = "DataInspectionFailed", "图片未通过审核"
            return httpx.Response(200, json={"output": output})
        if url == "https://oss.example.com/result.mp4":
            return httpx.Response(200, content=RESULT_MP4)
        return httpx.Response(404)


@pytest.fixture
def wan(monkeypatch, app) -> FakeWan:
    app.state.settings.dashscope_api_key = "sk-test-key"
    fake = FakeWan()
    monkeypatch.setattr(
        providers, "http_client", lambda: httpx.Client(transport=httpx.MockTransport(fake.handler))
    )
    return fake


def cover(admin: TestClient, book_id: str) -> dict:
    return admin.get(f"/api/admin/books/{book_id}/ai").json()["cover"]


def generate(admin: TestClient, book_id: str, **body):
    return admin.post(f"/api/admin/books/{book_id}/ai/cover-video", json=body or None)


def run_to_ready(admin, worker, advance, book_id: str) -> dict:
    assert generate(admin, book_id).status_code == 202
    assert worker.run_once() is True  # 提交
    advance(POLL)
    assert worker.run_once() is True  # RUNNING
    advance(POLL)
    assert worker.run_once() is True  # SUCCEEDED → 下载
    return cover(admin, book_id)


def test_cover_video_flow(admin, reader, app, worker, advance, ready_book, wan):
    book_id = ready_book["id"]
    admin.patch(f"/api/admin/books/{book_id}/ai", json={"cover_motion_prompt": "  小熊轻轻眨眼 "})
    initial = cover(admin, book_id)
    assert initial["motion_prompt"] == "小熊轻轻眨眼"
    assert initial["status"] == "none"
    assert initial["video_url"] is None

    res = generate(admin, book_id)
    assert res.status_code == 202, res.text
    assert generate(admin, book_id).json()["job_id"] == res.json()["job_id"]  # 不重复排队
    assert cover(admin, book_id)["status"] == "queued"

    # 提交：先上传首帧到服务商的临时存储，图生视频只给首帧（D99）
    assert worker.run_once() is True
    upload = next(r for r in wan.requests if str(r.url) == "https://oss.example.com")
    assert b'name="key"' in upload.content and b"dashscope-instant/abc/frame.jpg" in upload.content
    (submit,) = wan.submits()
    assert str(submit.url) == SUBMIT_URL
    assert submit.headers["X-DashScope-Async"] == "enable"
    assert submit.headers["X-DashScope-OssResourceResolve"] == "enable"
    body = json.loads(submit.content)
    assert body["model"] == "wan2.2-i2v-flash"
    assert body["input"]["img_url"] == "oss://dashscope-instant/abc/frame.jpg"
    assert "last_frame_url" not in body["input"]
    assert "小熊轻轻眨眼" in body["input"]["prompt"]
    assert "预言家日报" in body["input"]["prompt"] and "来回往复" in body["input"]["prompt"]
    # 管理员填了描述：不再让视觉模型写
    assert not any(r.url.path.endswith("/chat/completions") for r in wan.requests)
    assert "镜头移动" in body["input"]["negative_prompt"]
    # wan2.2 的时长固定 5 秒，不传
    assert body["parameters"] == {"resolution": "480P", "prompt_extend": True}

    # 等待查询期间不占用 Worker，界面继续轮询
    assert cover(admin, book_id)["status"] == "running"
    jobs = admin.get(f"/api/admin/books/{book_id}/ai").json()["running_jobs"]
    assert [(j["type"], j["status"]) for j in jobs] == [("ai_cover_video", "waiting")]
    assert worker.run_once() is False

    advance(POLL)
    assert worker.run_once() is True  # RUNNING
    assert cover(admin, book_id)["status"] == "running"
    advance(POLL)
    assert worker.run_once() is True  # SUCCEEDED
    done = cover(admin, book_id)
    assert done["status"] == "ready"
    assert done["error"] is None
    assert done["resolution"] == "480P" and done["duration_s"] == 5
    assert done["outdated"] is False and done["frame_changed"] is False
    assert done["video_url"] == f"/api/admin/books/{book_id}/ai/cover-video?v=1"
    assert len(wan.submits()) == 1

    # 后台预览：去掉了音轨；正放再倒放，首尾都是原画（24 帧 → 24 + 22 帧）
    res = admin.get(done["video_url"])
    assert res.status_code == 200
    assert res.headers["content-type"] == "video/mp4"
    with av.open(io.BytesIO(res.content)) as container:
        assert [s.type for s in container.streams] == ["video"]
        levels = [int(f.to_ndarray(format="gray").mean()) for f in container.decode(video=0)]
    assert len(levels) == 46
    assert levels[:24] == sorted(levels[:24]) and levels[24:] == sorted(levels[24:], reverse=True)
    assert abs(levels[-1] - levels[0]) < abs(levels[23] - levels[0])

    # 启用前读者看不到
    shelf = next(b for b in reader.get("/api/books").json() if b["id"] == book_id)
    assert shelf["cover_video_url"] is None
    assert reader.get(f"/api/books/{book_id}/cover-video").status_code == 404

    res = admin.put(f"/api/admin/books/{book_id}/ai/cover-video/enabled")
    assert res.status_code == 200
    assert res.json()["cover"]["enabled_at"] is not None
    shelf = next(b for b in reader.get("/api/books").json() if b["id"] == book_id)
    assert shelf["cover_video_url"] == f"/api/books/{book_id}/cover-video?v=1"
    detail = reader.get(f"/api/books/{book_id}").json()
    assert detail["cover_video_url"] == shelf["cover_video_url"]
    assert detail["cover_page_index"] == 0
    # iPad Safari 播放视频要用分段请求
    res = reader.get(shelf["cover_video_url"], headers={"Range": "bytes=0-99"})
    assert res.status_code == 206
    assert len(res.content) == 100

    admin.delete(f"/api/admin/books/{book_id}/ai/cover-video/enabled")
    assert reader.get(f"/api/books/{book_id}").json()["cover_video_url"] is None


def test_prompt_and_cover_changes(admin, reader, worker, advance, ready_book, wan):
    book_id = ready_book["id"]
    run_to_ready(admin, worker, advance, book_id)
    admin.put(f"/api/admin/books/{book_id}/ai/cover-video/enabled")

    admin.patch(f"/api/admin/books/{book_id}/ai", json={"cover_motion_prompt": "尾巴轻轻摆动"})
    changed = cover(admin, book_id)
    assert changed["outdated"] is True
    # 只改了动作描述：读者仍看到原来的动画
    assert reader.get(f"/api/books/{book_id}").json()["cover_video_url"] is not None

    # 换了封面：旧动画对不上，读者不再看到，也不能再启用
    admin.patch(f"/api/admin/books/{book_id}", json={"cover_page_index": 1})
    assert cover(admin, book_id)["frame_changed"] is True
    assert reader.get(f"/api/books/{book_id}").json()["cover_video_url"] is None
    assert reader.get(f"/api/books/{book_id}/cover-video").status_code == 404
    admin.delete(f"/api/admin/books/{book_id}/ai/cover-video/enabled")
    res = admin.put(f"/api/admin/books/{book_id}/ai/cover-video/enabled")
    assert res.status_code == 400
    assert "封面已更换" in res.json()["detail"]

    # 重新生成后恢复，版本号变化
    wan.poll_statuses = ["SUCCEEDED"]
    assert generate(admin, book_id).status_code == 202
    worker.run_once()
    advance(POLL)
    worker.run_once()
    regenerated = cover(admin, book_id)
    assert regenerated["frame_changed"] is False and regenerated["outdated"] is False
    assert regenerated["video_url"].endswith("?v=2")
    assert admin.put(f"/api/admin/books/{book_id}/ai/cover-video/enabled").status_code == 200


def test_provider_failure(admin, worker, advance, ready_book, wan):
    book_id = ready_book["id"]
    wan.poll_statuses = ["FAILED"]
    generate(admin, book_id)
    worker.run_once()
    advance(POLL)
    worker.run_once()
    failed = cover(admin, book_id)
    assert failed["status"] == "failed"
    assert "图片未通过审核" in failed["error"]
    assert admin.put(f"/api/admin/books/{book_id}/ai/cover-video/enabled").status_code == 400


def test_poll_errors_retry_then_time_out(admin, worker, advance, ready_book, wan):
    book_id = ready_book["id"]
    generate(admin, book_id)
    worker.run_once()
    # 查询出错（如网络抖动）不算失败：已经付费的任务稍后再查
    wan.poll_error = httpx.Response(500, json={"message": "Internal error"})
    advance(POLL)
    assert worker.run_once() is True
    assert cover(admin, book_id)["status"] == "running"

    wan.poll_error = None
    wan.poll_statuses = ["RUNNING"]
    advance(VIDEO_MAX_WAIT)
    assert worker.run_once() is True
    timed_out = cover(admin, book_id)
    assert timed_out["status"] == "failed"
    assert "超时" in timed_out["error"]


def test_restart_keeps_submitted_task(admin, app, worker, advance, ready_book, wan):
    """Worker 重启：已提交的任务继续查询，不重新提交（避免重复付费）。"""
    book_id = ready_book["id"]
    generate(admin, book_id)
    worker.run_once()
    with app.state.session_factory() as db:
        job = db.query(Job).filter(Job.type == "ai_cover_video").one()
        job.status = "running"  # 查询到一半时进程被杀
        db.commit()
    worker.recover()
    assert worker.run_once() is True
    advance(POLL)
    assert worker.run_once() is True
    assert cover(admin, book_id)["status"] == "ready"
    assert len(wan.submits()) == 1


def test_remote_video_limit(admin, app, worker, ready_book, pdf_bytes, wan):
    """服务商那边已有 MAX_REMOTE_VIDEOS 个视频任务时，新的视频任务先不提交，其他任务照常执行。"""
    from tests.conftest import upload

    book_id = ready_book["id"]
    other = upload(admin, pdf_bytes).json()
    # 其他书已占满服务商那边的名额
    with app.state.session_factory() as db:
        for i in range(MAX_REMOTE_VIDEOS):
            db.add(
                Job(
                    type="ai_cover_video",
                    book_id=other["id"],
                    status="waiting",
                    remote_task_id=f"other-{i}",
                    next_poll_at=None,
                )
            )
        db.commit()
    generate(admin, book_id)
    assert worker.run_once() is True  # 拆页照常
    assert admin.get(f"/api/admin/books/{other['id']}").json()["processing_status"] == "ready"
    assert worker.run_once() is False
    assert wan.submits() == []
    assert cover(admin, book_id)["status"] == "queued"


def test_unknown_model_fails_with_hint(admin, worker, ready_book, wan):
    book_id = ready_book["id"]
    res = admin.put(
        "/api/admin/ai/capabilities/video",
        json={"provider": "dashscope", "model": "wan2.5-t2v", "base_url": API, "options": {}},
    )
    assert res.status_code == 200, res.text
    generate(admin, book_id)
    worker.run_once()
    failed = cover(admin, book_id)
    assert failed["status"] == "failed"
    assert "图生视频" in failed["error"]
    assert wan.submits() == []


def test_keyframes_model_still_works(admin, worker, advance, ready_book, wan):
    """首尾帧模型（D96 用过）仍可选：首帧和尾帧都用同一张图。"""
    book_id = ready_book["id"]
    admin.put(
        "/api/admin/ai/capabilities/video",
        json={
            "provider": "dashscope",
            "model": "wan2.2-kf2v-flash",
            "base_url": API,
            "options": {},
        },
    )
    assert run_to_ready(admin, worker, advance, book_id)["status"] == "ready"
    (submit,) = wan.submits()
    assert str(submit.url) == KEYFRAMES_URL
    body = json.loads(submit.content)["input"]
    assert (
        body["first_frame_url"] == body["last_frame_url"] == "oss://dashscope-instant/abc/frame.jpg"
    )


def test_duration_sent_when_model_allows_choice(admin, worker, ready_book, wan):
    admin.put(
        "/api/admin/ai/capabilities/video",
        json={
            "provider": "dashscope",
            "model": "wan2.6-i2v-flash",
            "base_url": API,
            "options": {"duration": 3, "resolution": "1080P"},
        },
    )
    generate(admin, ready_book["id"])
    worker.run_once()
    (submit,) = wan.submits()
    assert json.loads(submit.content)["parameters"] == {
        "resolution": "1080P",
        "prompt_extend": True,
        "duration": 3,
    }


def test_requires_key(admin, app, ready_book):
    app.state.settings.dashscope_api_key = ""
    res = generate(admin, ready_book["id"])
    assert res.status_code == 400
    assert "DASHSCOPE_API_KEY" in res.json()["detail"]


def test_analysis_fills_cover_motion_draft(admin, worker, advance, ready_book, wan):
    book_id = ready_book["id"]
    wan.analysis = {
        "story": "故事",
        "characters": [{"name": "旁白", "is_narrator": True, "voice_prompt": "温柔"}],
        "pages": [{"page_index": 0, "lines": [], "motion_prompt": "封面上的小熊挥挥手"}],
        "spread_suggestions": [],
    }
    admin.post(f"/api/admin/books/{book_id}/ai/analyze")
    worker.run_once()
    assert cover(admin, book_id)["motion_prompt"] == "封面上的小熊挥挥手"

    # 管理员改过的不再被覆盖
    admin.patch(f"/api/admin/books/{book_id}/ai", json={"cover_motion_prompt": "小熊眨眼"})
    admin.post(f"/api/admin/books/{book_id}/ai/analyze")
    worker.run_once()
    assert cover(admin, book_id)["motion_prompt"] == "小熊眨眼"


def test_book_delete_removes_cover_video(admin, settings, worker, advance, ready_book, wan):
    book_id = ready_book["id"]
    run_to_ready(admin, worker, advance, book_id)
    path = storage.ai_cover_video_path(settings, book_id)
    assert path.is_file()
    assert admin.delete(f"/api/admin/books/{book_id}").status_code == 204
    assert not path.exists()


def test_empty_motion_is_written_from_cover(admin, worker, ready_book, wan):
    """没填动作描述时，先让视觉模型看封面写一句具体的，存为草稿后再提交（笼统的描述模型容易不动）。"""
    book_id = ready_book["id"]
    assert cover(admin, book_id)["motion_prompt"] is None
    generate(admin, book_id)
    worker.run_once()

    (chat,) = [r for r in wan.requests if r.url.path.endswith("/chat/completions")]
    content = json.loads(chat.content)["messages"][0]["content"]
    assert "会动的魔法照片" in content[0]["text"] and "来回往复" in content[0]["text"]
    assert content[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")

    assert cover(admin, book_id)["motion_prompt"] == "兔子眨眨眼，小老鼠的尾巴轻轻摆动"
    (submit,) = wan.submits()
    assert "兔子眨眨眼，小老鼠的尾巴轻轻摆动" in json.loads(submit.content)["input"]["prompt"]


def test_motion_writer_failure(admin, worker, ready_book, wan):
    book_id = ready_book["id"]
    wan.analysis = {"story": "没有 motion 字段"}
    generate(admin, book_id)
    worker.run_once()
    failed = cover(admin, book_id)
    assert failed["status"] == "failed"
    assert "自动写动作描述失败" in failed["error"]
    assert wan.submits() == []


def use_model(admin, model: str, **options) -> None:
    res = admin.put(
        "/api/admin/ai/capabilities/video",
        json={"provider": "dashscope", "model": model, "base_url": API, "options": options},
    )
    assert res.status_code == 200, res.text


def test_temporary_duration_and_resolution(admin, worker, advance, ready_book, wan):
    """生成封面动画时可临时换时长、清晰度（D79）：只对这一次生效，不算"需要重新生成"。"""
    book_id = ready_book["id"]
    use_model(admin, "wan2.6-i2v-flash")
    done_by_default = run_to_ready(admin, worker, advance, book_id)
    assert (done_by_default["duration_s"], done_by_default["resolution"]) == (5, "720P")

    wan.poll_statuses = ["SUCCEEDED"]
    assert generate(admin, book_id, duration=10, resolution="1080P").status_code == 202
    worker.run_once()
    advance(POLL)
    worker.run_once()
    chosen = json.loads(wan.submits()[-1].content)["parameters"]
    assert chosen == {"resolution": "1080P", "prompt_extend": True, "duration": 10}
    done = cover(admin, book_id)
    assert (done["duration_s"], done["resolution"]) == (10, "1080P")
    assert done["outdated"] is False  # AI 配置里的默认值仍是 5 秒 · 720P，但按生成时的参数比较

    # 改了动作描述才算过期
    admin.patch(f"/api/admin/books/{book_id}/ai", json={"cover_motion_prompt": "小熊跳一跳"})
    assert cover(admin, book_id)["outdated"] is True


def test_temporary_options_are_validated(admin, ready_book, wan):
    book_id = ready_book["id"]
    res = generate(admin, book_id, resolution="4K")
    assert res.status_code == 400 and "清晰度" in res.json()["detail"]
    res = generate(admin, book_id, duration=10)  # 默认模型 wan2.2 固定 5 秒
    assert res.status_code == 400 and "5 秒" in res.json()["detail"]
    assert cover(admin, book_id)["status"] == "none"
    assert generate(admin, book_id, resolution="480P").status_code == 202

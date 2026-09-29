"""单元朗读：合成、拼接、重新生成、全部生成、Voice Ready 与阅读端（docs/06 第 6.4、6.7、7 节）。"""

import base64
import io
import json
import math
import struct
import wave

import av
import httpx
import pytest
from fastapi.testclient import TestClient

from app.ai import providers
from app.books import storage

SYNTH_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
LINE_SECONDS = 0.5

ANALYSIS = {
    "story": "波西遇见了大怪兽。",
    "characters": [
        {"name": "旁白", "is_narrator": True, "voice_prompt": "温柔女声"},
        {"name": "波西", "is_narrator": False, "voice_prompt": "小女孩"},
        {"name": "大怪兽", "is_narrator": False, "voice_prompt": "低沉憨厚"},
    ],
    "pages": [
        {
            "page_index": 2,
            "lines": [
                {"character": "旁白", "text": "门开了。"},
                {"character": "波西", "text": "哦，天哪！"},
            ],
        },
        {"page_index": 3, "lines": [{"character": "大怪兽", "text": "嗷呜！"}]},
        {"page_index": 4, "lines": []},
    ],
    "spread_suggestions": [],
}


def make_wav(seconds: float = LINE_SECONDS, rate: int = 16000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(
            b"".join(
                struct.pack("<h", int(8000 * math.sin(2 * math.pi * 440 * i / rate)))
                for i in range(int(seconds * rate))
            )
        )
    return buf.getvalue()


class FakeDashscope:
    """假的百炼：看图分析、音色设计、合成（返回下载地址）、下载音频。"""

    def __init__(self):
        self.requests: list[httpx.Request] = []
        self.synth_error: httpx.Response | None = None

    def synth_requests(self) -> list[dict]:
        return [json.loads(r.content) for r in self.requests if str(r.url) == SYNTH_URL]

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        if path.endswith("/chat/completions"):
            content = json.dumps(ANALYSIS, ensure_ascii=False)
            return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})
        if path.endswith("/customization"):
            prompt = json.loads(request.content)["input"]["voice_prompt"]
            return httpx.Response(
                200,
                json={
                    "output": {
                        "voice": f"voice-{prompt}",
                        "preview_audio": {"data": base64.b64encode(make_wav(0.1)).decode()},
                    }
                },
            )
        if str(request.url) == SYNTH_URL:
            if self.synth_error is not None:
                return self.synth_error
            return httpx.Response(
                200, json={"output": {"audio": {"url": "https://oss.example.com/line.wav"}}}
            )
        if request.url.host == "oss.example.com":
            return httpx.Response(200, content=make_wav())
        return httpx.Response(404)


@pytest.fixture
def fake(monkeypatch, app) -> FakeDashscope:
    app.state.settings.dashscope_api_key = "sk-test-key"
    fake = FakeDashscope()
    monkeypatch.setattr(
        providers, "http_client", lambda: httpx.Client(transport=httpx.MockTransport(fake.handler))
    )
    return fake


@pytest.fixture
def analyzed(admin: TestClient, worker, ready_book: dict, fake) -> dict:
    """分析过的绘本：第 3–4 页分别生成，第 3 页两行台词（旁白、波西），第 4 页大怪兽。"""
    book_id = ready_book["id"]
    admin.post(f"/api/admin/books/{book_id}/ai/analyze")
    assert worker.run_once() is True
    return ready_book


def book_ai(admin: TestClient, book_id: str) -> dict:
    return admin.get(f"/api/admin/books/{book_id}/ai").json()


def unit_at(admin: TestClient, book_id: str, page: int) -> dict:
    units = [u for s in book_ai(admin, book_id)["spreads"] for u in s["units"]]
    return next(u for u in units if u["first_page_index"] == page)


def design_voices(admin: TestClient, worker, book_id: str, *names: str) -> None:
    for c in book_ai(admin, book_id)["characters"]:
        if c["name"] in names:
            res = admin.post(f"/api/admin/books/{book_id}/ai/characters/{c['id']}/voice")
            assert res.status_code == 202, res.text
            assert worker.run_once() is True


def test_generate_unit_audio(admin, settings, worker, analyzed, fake):
    book_id = analyzed["id"]
    design_voices(admin, worker, book_id, "旁白", "波西")
    unit = unit_at(admin, book_id, 2)
    assert unit["audio_status"] == "none"
    assert unit["audio_url"] is None

    res = admin.post(f"/api/admin/ai/units/{unit['id']}/audio")
    assert res.status_code == 202, res.text
    # 重复点击不重复排队
    assert admin.post(f"/api/admin/ai/units/{unit['id']}/audio").json() == res.json()
    assert unit_at(admin, book_id, 2)["audio_status"] == "queued"
    assert worker.run_once() is True
    assert worker.run_once() is False

    # 逐行用各自的音色合成
    assert fake.synth_requests() == [
        {
            "model": "qwen3-tts-vd-2026-01-26",
            "input": {"text": "门开了。", "voice": "voice-温柔女声"},
        },
        {
            "model": "qwen3-tts-vd-2026-01-26",
            "input": {"text": "哦，天哪！", "voice": "voice-小女孩"},
        },
    ]
    done = unit_at(admin, book_id, 2)
    assert done["audio_status"] == "ready"
    assert done["audio_error"] is None
    assert done["audio_outdated"] is False
    assert done["audio_version"] == 1
    # 两行各 0.5 秒 + 行间停顿 0.4 秒
    assert done["audio_duration_ms"] == 1400
    assert done["audio_url"] == f"/api/admin/ai/units/{unit['id']}/audio?v=1"

    res = admin.get(done["audio_url"])
    assert res.status_code == 200
    assert res.headers["content-type"] == "audio/mp4"
    with av.open(io.BytesIO(res.content)) as container:
        stream = container.streams.audio[0]
        assert stream.codec_context.name == "aac"
        assert abs(float(container.duration / 1e6) - 1.4) < 0.1
    assert storage.ai_audio_path(settings, book_id, unit["id"]).is_file()


def test_line_without_speaker_uses_narrator(admin, worker, analyzed, fake):
    book_id = analyzed["id"]
    design_voices(admin, worker, book_id, "旁白")
    unit = unit_at(admin, book_id, 4)
    admin.patch(
        f"/api/admin/ai/units/{unit['id']}",
        json={"lines": [{"character_id": None, "text": "后来呢？"}, {"text": "  "}]},
    )
    assert admin.post(f"/api/admin/ai/units/{unit['id']}/audio").status_code == 202
    worker.run_once()
    assert fake.synth_requests()[-1]["input"] == {"text": "后来呢？", "voice": "voice-温柔女声"}
    assert unit_at(admin, book_id, 4)["audio_duration_ms"] == 500


def test_edit_marks_audio_outdated(admin, worker, analyzed, fake):
    book_id = analyzed["id"]
    design_voices(admin, worker, book_id, "旁白", "波西")
    unit = unit_at(admin, book_id, 2)
    admin.post(f"/api/admin/ai/units/{unit['id']}/audio")
    worker.run_once()

    edited = admin.patch(
        f"/api/admin/ai/units/{unit['id']}",
        json={"lines": [{"character_id": unit["lines"][0]["character_id"], "text": "门开啦。"}]},
    ).json()
    assert edited["audio_outdated"] is True
    # 旧朗读仍可试听，直到重新生成
    assert edited["audio_url"] is not None
    assert unit_at(admin, book_id, 2)["audio_outdated"] is True

    admin.post(f"/api/admin/ai/units/{unit['id']}/audio")
    worker.run_once()
    regenerated = unit_at(admin, book_id, 2)
    assert regenerated["audio_outdated"] is False
    assert regenerated["audio_version"] == 2
    assert regenerated["audio_url"].endswith("?v=2")


def test_new_voice_marks_audio_outdated(admin, worker, analyzed, fake):
    book_id = analyzed["id"]
    design_voices(admin, worker, book_id, "大怪兽")
    unit = unit_at(admin, book_id, 3)
    admin.post(f"/api/admin/ai/units/{unit['id']}/audio")
    worker.run_once()
    assert unit_at(admin, book_id, 3)["audio_outdated"] is False

    monster = next(c for c in book_ai(admin, book_id)["characters"] if c["name"] == "大怪兽")
    admin.patch(
        f"/api/admin/books/{book_id}/ai/characters/{monster['id']}",
        json={"voice_prompt": "更凶一点"},
    )
    design_voices(admin, worker, book_id, "大怪兽")
    assert unit_at(admin, book_id, 3)["audio_outdated"] is True


def test_audio_requires_voices_and_lines(admin, app, worker, analyzed, fake):
    book_id = analyzed["id"]
    design_voices(admin, worker, book_id, "旁白")
    unit = unit_at(admin, book_id, 2)
    res = admin.post(f"/api/admin/ai/units/{unit['id']}/audio")
    assert res.status_code == 400
    assert res.json()["detail"] == "请先为角色「波西」生成音色"

    empty = unit_at(admin, book_id, 4)
    res = admin.post(f"/api/admin/ai/units/{empty['id']}/audio")
    assert res.status_code == 400
    assert "没有台词" in res.json()["detail"]

    app.state.settings.dashscope_api_key = ""
    res = admin.post(f"/api/admin/ai/units/{unit['id']}/audio")
    assert res.status_code == 400
    assert "DASHSCOPE_API_KEY" in res.json()["detail"]

    assert admin.post("/api/admin/ai/units/nope/audio").status_code == 404
    assert fake.synth_requests() == []


def test_failure_keeps_previous_audio(admin, worker, analyzed, fake):
    book_id = analyzed["id"]
    design_voices(admin, worker, book_id, "大怪兽")
    unit = unit_at(admin, book_id, 3)
    admin.post(f"/api/admin/ai/units/{unit['id']}/audio")
    worker.run_once()
    first_url = unit_at(admin, book_id, 3)["audio_url"]

    fake.synth_error = httpx.Response(400, json={"code": "Arrearage", "message": "余额不足"})
    admin.post(f"/api/admin/ai/units/{unit['id']}/audio")
    worker.run_once()
    failed = unit_at(admin, book_id, 3)
    assert failed["audio_status"] == "failed"
    assert "余额不足" in failed["audio_error"]
    assert failed["audio_url"] == first_url
    assert admin.get(first_url).status_code == 200


def test_generate_all(admin, worker, analyzed, fake):
    book_id = analyzed["id"]
    url = f"/api/admin/books/{book_id}/ai/generate-all?type=audio"
    res = admin.post(url)
    assert res.status_code == 400
    assert "旁白" in res.json()["detail"] and "大怪兽" in res.json()["detail"]

    design_voices(admin, worker, book_id, "旁白", "波西", "大怪兽")
    # 第 2 页（两行）和第 3 页有台词；其余单元没有台词，不生成
    res = admin.post(url)
    assert res.status_code == 202, res.text
    assert res.json() == {"queued": 2}
    # 已在队列里的不重复放入
    assert admin.post(url).json() == {"queued": 0}
    running = book_ai(admin, book_id)["running_jobs"]
    assert sorted(j["type"] for j in running) == ["ai_tts_unit", "ai_tts_unit"]

    while worker.run_once():
        pass
    assert unit_at(admin, book_id, 2)["audio_status"] == "ready"
    assert unit_at(admin, book_id, 3)["audio_status"] == "ready"
    assert admin.post(url).json() == {"queued": 0}

    # 改了一个单元的台词：只重新生成这一个
    unit = unit_at(admin, book_id, 3)
    admin.patch(
        f"/api/admin/ai/units/{unit['id']}",
        json={"lines": [{"character_id": unit["lines"][0]["character_id"], "text": "嗷！"}]},
    )
    assert admin.post(url).json() == {"queued": 1}


def test_spread_mode_change_removes_audio(admin, settings, worker, analyzed, fake):
    book_id = analyzed["id"]
    design_voices(admin, worker, book_id, "旁白", "波西")
    unit = unit_at(admin, book_id, 2)
    admin.post(f"/api/admin/ai/units/{unit['id']}/audio")
    worker.run_once()
    path = storage.ai_audio_path(settings, book_id, unit["id"])
    assert path.is_file()

    admin.put(f"/api/admin/books/{book_id}/ai/spreads/2", json={"mode": "merged"})
    merged = unit_at(admin, book_id, 2)
    assert merged["audio_status"] == "none"
    assert merged["audio_url"] is None
    assert not path.exists()


def test_unit_audio_is_admin_only(admin, reader, worker, analyzed, fake):
    book_id = analyzed["id"]
    design_voices(admin, worker, book_id, "大怪兽")
    unit = unit_at(admin, book_id, 3)
    admin.post(f"/api/admin/ai/units/{unit['id']}/audio")
    worker.run_once()
    assert reader.get(unit_at(admin, book_id, 3)["audio_url"]).status_code == 403


# ---------- Voice Ready 与阅读端 ----------


def generate_audio(admin: TestClient, worker, book_id: str, page: int) -> dict:
    unit = unit_at(admin, book_id, page)
    assert admin.post(f"/api/admin/ai/units/{unit['id']}/audio").status_code == 202
    assert worker.run_once() is True
    return unit_at(admin, book_id, page)


def test_voice_ready_controls_reader_audio(admin, reader, worker, analyzed, fake):
    book_id = analyzed["id"]
    ready_url = f"/api/admin/books/{book_id}/ai/voice-ready"

    # 还没有任何朗读时不能确认
    res = admin.put(ready_url)
    assert res.status_code == 400
    assert res.json()["detail"] == "还没有生成任何朗读"

    design_voices(admin, worker, book_id, "大怪兽")
    unit = generate_audio(admin, worker, book_id, 3)

    # 确认前：读者拿不到朗读
    shelf_book = next(b for b in reader.get("/api/books").json() if b["id"] == book_id)
    assert shelf_book["voice_ready"] is False
    assert shelf_book["dance_ready"] is False
    detail = reader.get(f"/api/books/{book_id}").json()
    assert detail["read_order"] == "left_first"
    assert detail["units"] == []
    audio_path = f"/api/books/{book_id}/ai/audio/{unit['id']}?v=1"
    assert reader.get(audio_path).status_code == 404

    res = admin.put(ready_url)
    assert res.status_code == 200, res.text
    assert res.json()["voice_ready_at"] is not None

    shelf_book = next(b for b in reader.get("/api/books").json() if b["id"] == book_id)
    assert shelf_book["voice_ready"] is True
    # 只列出已生成朗读的单元
    assert reader.get(f"/api/books/{book_id}").json()["units"] == [
        {"pages": [3], "audio_url": audio_path, "audio_duration_ms": 500, "video_url": None}
    ]
    res = reader.get(audio_path)
    assert res.status_code == 200
    assert res.headers["content-type"] == "audio/mp4"
    assert "immutable" in res.headers["cache-control"]

    res = admin.delete(ready_url)
    assert res.status_code == 200
    assert res.json()["voice_ready_at"] is None
    assert reader.get(f"/api/books/{book_id}").json()["units"] == []
    assert reader.get(audio_path).status_code == 404


def test_reader_units_follow_spreads_and_order(admin, reader, worker, analyzed, fake):
    book_id = analyzed["id"]
    design_voices(admin, worker, book_id, "旁白", "波西", "大怪兽")
    admin.patch(f"/api/admin/books/{book_id}/ai", json={"read_order": "right_first"})
    # 第 3–4 页合并生成：一个单元覆盖两页
    admin.put(f"/api/admin/books/{book_id}/ai/spreads/2", json={"mode": "merged"})
    merged = generate_audio(admin, worker, book_id, 2)
    assert merged["page_count"] == 2
    admin.put(f"/api/admin/books/{book_id}/ai/voice-ready")

    detail = reader.get(f"/api/books/{book_id}").json()
    assert detail["read_order"] == "right_first"
    assert [u["pages"] for u in detail["units"]] == [[2, 3]]
    assert detail["units"][0]["audio_url"].endswith(f"/ai/audio/{merged['id']}?v=1")


def test_reader_audio_rejects_other_books_and_unlisted(
    admin, reader, worker, analyzed, pdf_bytes, fake
):
    from tests.conftest import upload

    book_id = analyzed["id"]
    design_voices(admin, worker, book_id, "大怪兽")
    unit = generate_audio(admin, worker, book_id, 3)
    admin.put(f"/api/admin/books/{book_id}/ai/voice-ready")
    audio_path = f"/api/books/{book_id}/ai/audio/{unit['id']}"
    assert reader.get(audio_path).status_code == 200

    other = upload(admin, pdf_bytes).json()
    worker.run_once()
    assert reader.get(f"/api/books/{other['id']}/ai/audio/{unit['id']}").status_code == 404

    # 下架后读者看不到；管理员仍可预览（与页面图片一致）
    admin.patch(f"/api/admin/books/{book_id}", json={"visibility": "unlisted"})
    assert reader.get(audio_path).status_code == 404
    assert admin.get(audio_path).status_code == 200


def test_reanalysis_clears_voice_ready(admin, worker, analyzed, fake):
    book_id = analyzed["id"]
    design_voices(admin, worker, book_id, "大怪兽")
    generate_audio(admin, worker, book_id, 3)
    admin.put(f"/api/admin/books/{book_id}/ai/voice-ready")
    admin.post(f"/api/admin/books/{book_id}/ai/analyze")
    worker.run_once()
    assert book_ai(admin, book_id)["voice_ready_at"] is None


# ---------- 开页的朗读 / 动画开关（D95）与生成本开页朗读 ----------


def set_switches(admin: TestClient, book_id: str, first_page: int, **body) -> dict:
    res = admin.patch(f"/api/admin/books/{book_id}/ai/spreads/{first_page}", json=body)
    assert res.status_code == 200, res.text
    return res.json()


def spread_at(admin: TestClient, book_id: str, first_page: int) -> dict:
    return next(s for s in book_ai(admin, book_id)["spreads"] if s["left_page_index"] == first_page)


def test_spread_audio_generates_every_unit(admin, worker, analyzed, fake):
    book_id = analyzed["id"]
    design_voices(admin, worker, book_id, "旁白", "波西", "大怪兽")
    url = f"/api/admin/books/{book_id}/ai/spreads/2/audio"
    res = admin.post(url)
    assert res.status_code == 202, res.text
    assert res.json() == {"queued": 2}
    while worker.run_once():
        pass
    assert [u["audio_status"] for u in spread_at(admin, book_id, 2)["units"]] == ["ready"] * 2
    # 与单元上的按钮一样：已是最新也重新生成
    assert admin.post(url).json() == {"queued": 2}

    # 第 5–6 页没有台词
    res = admin.post(f"/api/admin/books/{book_id}/ai/spreads/4/audio")
    assert res.status_code == 400
    assert "没有台词" in res.json()["detail"]
    assert admin.post(f"/api/admin/books/{book_id}/ai/spreads/99/audio").status_code == 404


def test_disabled_spread_is_skipped(admin, worker, analyzed, fake):
    book_id = analyzed["id"]
    # 大怪兽（第 4 页）没有音色，但所在开页关闭了朗读，全部生成不会因此报错
    design_voices(admin, worker, book_id, "旁白", "波西")
    spread = set_switches(admin, book_id, 2, audio_enabled=False)
    assert spread["audio_enabled"] is False
    assert spread["video_enabled"] is True
    assert [u["audio_enabled"] for u in spread["units"]] == [False, False]

    generate_all = f"/api/admin/books/{book_id}/ai/generate-all?type=audio"
    assert admin.post(generate_all).json() == {"queued": 0}
    unit = unit_at(admin, book_id, 2)
    res = admin.post(f"/api/admin/ai/units/{unit['id']}/audio")
    assert res.status_code == 400
    assert res.json()["detail"] == "这个开页已关闭朗读"
    assert admin.post(f"/api/admin/books/{book_id}/ai/spreads/2/audio").status_code == 400

    set_switches(admin, book_id, 2, audio_enabled=True)
    res = admin.post(generate_all)
    assert res.status_code == 400
    assert "大怪兽" in res.json()["detail"]


def test_disabled_spread_hidden_from_reader(admin, reader, worker, analyzed, fake):
    book_id = analyzed["id"]
    design_voices(admin, worker, book_id, "大怪兽")
    unit = generate_audio(admin, worker, book_id, 3)
    admin.put(f"/api/admin/books/{book_id}/ai/voice-ready")
    audio_path = f"/api/books/{book_id}/ai/audio/{unit['id']}"
    assert len(reader.get(f"/api/books/{book_id}").json()["units"]) == 1

    set_switches(admin, book_id, 2, audio_enabled=False)
    assert reader.get(f"/api/books/{book_id}").json()["units"] == []
    assert reader.get(audio_path).status_code == 404
    # 唯一的朗读所在开页关闭了，不能再确认 Voice Ready
    admin.delete(f"/api/admin/books/{book_id}/ai/voice-ready")
    assert admin.put(f"/api/admin/books/{book_id}/ai/voice-ready").status_code == 400

    # 重新打开：原来的朗读还在
    set_switches(admin, book_id, 2, audio_enabled=True)
    assert admin.put(f"/api/admin/books/{book_id}/ai/voice-ready").status_code == 200
    assert reader.get(audio_path).status_code == 200


def test_disable_cancels_queued_audio(admin, app, worker, analyzed, fake):
    book_id = analyzed["id"]
    design_voices(admin, worker, book_id, "大怪兽")
    unit = unit_at(admin, book_id, 3)
    admin.post(f"/api/admin/ai/units/{unit['id']}/audio")
    assert unit_at(admin, book_id, 3)["audio_status"] == "queued"

    set_switches(admin, book_id, 2, audio_enabled=False)
    assert unit_at(admin, book_id, 3)["audio_status"] == "none"
    assert book_ai(admin, book_id)["running_jobs"] == []
    assert worker.run_once() is False


def test_worker_skips_unit_disabled_after_claim(admin, app, worker, analyzed, fake):
    """Worker 开始合成前发现开关已关（如关开关时任务刚被领走），就放弃。"""
    from app.models import AiUnit

    book_id = analyzed["id"]
    design_voices(admin, worker, book_id, "大怪兽")
    unit = unit_at(admin, book_id, 3)
    admin.post(f"/api/admin/ai/units/{unit['id']}/audio")
    with app.state.session_factory() as db:
        db.get(AiUnit, unit["id"]).audio_enabled = False
        db.commit()
    assert worker.run_once() is True
    assert fake.synth_requests() == []
    assert unit_at(admin, book_id, 3)["audio_status"] == "none"
    assert book_ai(admin, book_id)["running_jobs"] == []


def test_switches_survive_spread_mode_changes(admin, analyzed, fake):
    book_id = analyzed["id"]
    set_switches(admin, book_id, 2, audio_enabled=False, video_enabled=False)
    merged = admin.put(f"/api/admin/books/{book_id}/ai/spreads/2", json={"mode": "merged"}).json()
    assert (merged["audio_enabled"], merged["video_enabled"]) == (False, False)
    separate = admin.put(
        f"/api/admin/books/{book_id}/ai/spreads/2", json={"mode": "separate"}
    ).json()
    assert [(u["audio_enabled"], u["video_enabled"]) for u in separate["units"]] == [
        (False, False),
        (False, False),
    ]
    # 其他开页不受影响
    assert spread_at(admin, book_id, 4)["audio_enabled"] is True

    # 单页开页（封面）也能设置
    cover = set_switches(admin, book_id, 0, audio_enabled=False)
    assert cover["right_page_index"] == 0 and cover["audio_enabled"] is False

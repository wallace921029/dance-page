"""角色音色：设计、试听、重新生成、失败提示（docs/06 第 6.3 节）。"""

import base64
import json
from collections.abc import Callable

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.ai import providers
from app.books import storage

WAV = b"RIFF-fake-wav-bytes"
CUSTOMIZATION_URL = "https://dashscope.aliyuncs.com/api/v1/services/audio/tts/customization"


@pytest.fixture
def fake_dashscope(monkeypatch) -> Callable[..., list[httpx.Request]]:
    """假的百炼：音色设计按顺序返回 voice-1、voice-2…；vision 返回给定的分析结果。"""

    def install(*, fail: httpx.Response | None = None, analysis: dict | None = None):
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            if request.url.path.endswith("/chat/completions"):
                content = json.dumps(analysis, ensure_ascii=False)
                return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})
            if fail is not None:
                return fail
            n = sum(1 for r in requests if r.url.path.endswith("/customization"))
            return httpx.Response(
                200,
                json={
                    "output": {
                        "voice": f"voice-{n}",
                        "preview_audio": {"data": base64.b64encode(WAV).decode()},
                    }
                },
            )

        monkeypatch.setattr(
            providers, "http_client", lambda: httpx.Client(transport=httpx.MockTransport(handler))
        )
        return requests

    return install


@pytest.fixture
def keyed(app: FastAPI) -> FastAPI:
    app.state.settings.dashscope_api_key = "sk-test-key"
    return app


def add_character(admin: TestClient, book_id: str, **body) -> dict:
    res = admin.post(f"/api/admin/books/{book_id}/ai/characters", json=body)
    assert res.status_code == 201, res.text
    return res.json()


def get_character(admin: TestClient, book_id: str, character_id: int) -> dict:
    data = admin.get(f"/api/admin/books/{book_id}/ai").json()
    return next(c for c in data["characters"] if c["id"] == character_id)


def design(admin: TestClient, book_id: str, character_id: int):
    return admin.post(f"/api/admin/books/{book_id}/ai/characters/{character_id}/voice")


def test_design_voice_and_preview(admin, keyed, worker, ready_book, fake_dashscope):
    book_id = ready_book["id"]
    requests = fake_dashscope()
    char = add_character(admin, book_id, name="波西", voice_prompt="  5岁小女孩，声音清脆  ")
    assert char["voice"] is None
    assert char["voice_status"] == "none"

    res = design(admin, book_id, char["id"])
    assert res.status_code == 202, res.text
    # 重复点击不重复排队
    assert design(admin, book_id, char["id"]).json()["job_id"] == res.json()["job_id"]
    queued = get_character(admin, book_id, char["id"])
    assert queued["voice_status"] == "queued"
    ai = admin.get(f"/api/admin/books/{book_id}/ai").json()
    assert [j["type"] for j in ai["running_jobs"]] == ["ai_voice"]

    assert worker.run_once() is True
    assert worker.run_once() is False

    (req,) = requests
    assert str(req.url) == CUSTOMIZATION_URL
    assert req.headers["Authorization"] == "Bearer sk-test-key"
    body = json.loads(req.content)
    assert body["model"] == "qwen-voice-design"
    assert body["input"]["action"] == "create"
    assert body["input"]["target_model"] == "qwen3-tts-vd-2026-01-26"
    assert body["input"]["voice_prompt"] == "5岁小女孩，声音清脆"
    assert body["input"]["preferred_name"] == f"c{char['id']}"
    # 没有台词时用默认的试听句
    assert "波西" in body["input"]["preview_text"]

    ready = get_character(admin, book_id, char["id"])
    assert ready["voice_status"] == "ready"
    assert ready["voice_error"] is None
    assert ready["voice_outdated"] is False
    voice = ready["voice"]
    assert voice["provider"] == "dashscope"
    assert voice["tts_model"] == "qwen3-tts-vd-2026-01-26"

    res = admin.get(voice["preview_url"])
    assert res.status_code == 200
    assert res.content == WAV
    assert res.headers["content-type"] == "audio/wav"


def test_preview_is_admin_only(admin, reader, keyed, worker, ready_book, fake_dashscope):
    book_id = ready_book["id"]
    fake_dashscope()
    char = add_character(admin, book_id, name="旁白", is_narrator=True, voice_prompt="温柔女声")
    design(admin, book_id, char["id"])
    worker.run_once()
    url = get_character(admin, book_id, char["id"])["voice"]["preview_url"]
    assert reader.get(url).status_code == 403
    # 别的绘本的地址取不到
    other = url.replace(book_id, "0" * 32)
    assert admin.get(other).status_code == 404


def test_redesign_replaces_voice(admin, settings, keyed, worker, ready_book, fake_dashscope):
    book_id = ready_book["id"]
    fake_dashscope()
    char = add_character(admin, book_id, name="波西", voice_prompt="小女孩")
    design(admin, book_id, char["id"])
    worker.run_once()
    first = get_character(admin, book_id, char["id"])["voice"]

    # 改了音色描述：提示需要重新生成
    admin.patch(
        f"/api/admin/books/{book_id}/ai/characters/{char['id']}",
        json={"voice_prompt": "更活泼的小女孩"},
    )
    assert get_character(admin, book_id, char["id"])["voice_outdated"] is True

    design(admin, book_id, char["id"])
    worker.run_once()
    second = get_character(admin, book_id, char["id"])
    assert second["voice_outdated"] is False
    assert second["voice"]["voice_prompt_used"] == "更活泼的小女孩"
    # 地址变化，浏览器不会继续用缓存里的旧试听
    assert second["voice"]["preview_url"] != first["preview_url"]
    assert admin.get(second["voice"]["preview_url"]).status_code == 200
    # 旧音色的记录和试听文件都已替换，只剩一个
    voices_dir = storage.ai_dir(settings, book_id) / "voices"
    assert [p.name for p in voices_dir.iterdir()] == [f"{second['voice']['id']}.wav"]


def test_preview_text_uses_first_line(admin, keyed, worker, ready_book, fake_dashscope):
    book_id = ready_book["id"]
    analysis = {
        "story": "故事",
        "characters": [
            {"name": "旁白", "is_narrator": True, "voice_prompt": "温柔女声"},
            {"name": "大怪兽", "is_narrator": False, "voice_prompt": "低沉憨厚"},
        ],
        "pages": [
            {"page_index": 3, "lines": [{"character": "大怪兽", "text": "嗷呜！我来啦！"}]},
            {"page_index": 5, "lines": [{"character": "大怪兽", "text": "再见"}]},
        ],
        "spread_suggestions": [],
    }
    requests = fake_dashscope(analysis=analysis)
    admin.post(f"/api/admin/books/{book_id}/ai/analyze")
    worker.run_once()
    chars = admin.get(f"/api/admin/books/{book_id}/ai").json()["characters"]
    monster = next(c for c in chars if c["name"] == "大怪兽")

    design(admin, book_id, monster["id"])
    worker.run_once()
    body = json.loads(requests[-1].content)
    assert body["input"]["preview_text"] == "嗷呜！我来啦！"


def test_failure_is_shown_until_next_success(admin, keyed, worker, ready_book, fake_dashscope):
    book_id = ready_book["id"]
    fake_dashscope(fail=httpx.Response(400, json={"code": "Arrearage", "message": "余额不足"}))
    char = add_character(admin, book_id, name="波西", voice_prompt="小女孩")
    design(admin, book_id, char["id"])
    worker.run_once()
    failed = get_character(admin, book_id, char["id"])
    assert failed["voice_status"] == "failed"
    assert "余额不足" in failed["voice_error"]
    assert failed["voice"] is None

    fake_dashscope()
    design(admin, book_id, char["id"])
    worker.run_once()
    ok = get_character(admin, book_id, char["id"])
    assert ok["voice_status"] == "ready"
    assert ok["voice_error"] is None


def test_design_requires_prompt_and_key(admin, app, ready_book):
    book_id = ready_book["id"]
    char = add_character(admin, book_id, name="波西")
    res = design(admin, book_id, char["id"])
    assert res.status_code == 400
    assert "音色描述" in res.json()["detail"]

    admin.patch(
        f"/api/admin/books/{book_id}/ai/characters/{char['id']}", json={"voice_prompt": "小女孩"}
    )
    app.state.settings.dashscope_api_key = ""
    res = design(admin, book_id, char["id"])
    assert res.status_code == 400
    assert "DASHSCOPE_API_KEY" in res.json()["detail"]

    assert design(admin, book_id, 999999).status_code == 404


def test_unsupported_tts_model_fails_with_hint(admin, keyed, worker, ready_book, fake_dashscope):
    book_id = ready_book["id"]
    requests = fake_dashscope()
    res = admin.put(
        "/api/admin/ai/capabilities/tts",
        json={
            "provider": "dashscope",
            "model": "cosyvoice-v3-plus",
            "base_url": "https://dashscope.aliyuncs.com/api/v1",
            "options": {},
        },
    )
    assert res.status_code == 200, res.text
    char = add_character(admin, book_id, name="波西", voice_prompt="小女孩")
    design(admin, book_id, char["id"])
    worker.run_once()
    failed = get_character(admin, book_id, char["id"])
    assert failed["voice_status"] == "failed"
    assert "qwen3-tts-vd" in failed["voice_error"]
    assert requests == []


def test_voice_follows_tts_model(admin, keyed, worker, ready_book, fake_dashscope):
    """音色与"服务商 + 合成模型"绑定：换模型后显示未生成，切回来原音色还在（D78）。"""
    book_id = ready_book["id"]
    fake_dashscope()
    char = add_character(admin, book_id, name="波西", voice_prompt="小女孩")
    design(admin, book_id, char["id"])
    worker.run_once()
    voice_id = get_character(admin, book_id, char["id"])["voice"]["id"]

    def use_model(model: str):
        admin.put(
            "/api/admin/ai/capabilities/tts",
            json={
                "provider": "dashscope",
                "model": model,
                "base_url": "https://dashscope.aliyuncs.com/api/v1",
                "options": {},
            },
        )

    use_model("qwen3-tts-vd-2099-01-01")
    other = get_character(admin, book_id, char["id"])
    assert other["voice"] is None
    assert other["voice_status"] == "none"

    use_model("qwen3-tts-vd-2026-01-26")
    assert get_character(admin, book_id, char["id"])["voice"]["id"] == voice_id


def test_delete_character_removes_preview(
    admin, settings, keyed, worker, ready_book, fake_dashscope
):
    book_id = ready_book["id"]
    fake_dashscope()
    char = add_character(admin, book_id, name="波西", voice_prompt="小女孩")
    design(admin, book_id, char["id"])
    worker.run_once()
    voice_id = get_character(admin, book_id, char["id"])["voice"]["id"]
    path = storage.ai_voice_path(settings, book_id, voice_id)
    assert path.is_file()

    assert admin.delete(f"/api/admin/books/{book_id}/ai/characters/{char['id']}").status_code == 200
    assert not path.exists()

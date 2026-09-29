from collections.abc import Callable

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.ai import providers

DASHSCOPE_KEY = "sk-dashscope-secret-1234"
ARK_KEY = "ark-secret-key-5678"


def get_settings(admin: TestClient) -> dict:
    res = admin.get("/api/admin/ai/settings")
    assert res.status_code == 200, res.text
    return res.json()


def provider(settings: dict, provider_id: str) -> dict:
    return next(p for p in settings["providers"] if p["id"] == provider_id)


def field(settings: dict, provider_id: str, key: str) -> dict:
    return next(f for f in provider(settings, provider_id)["fields"] if f["key"] == key)


def capability(settings: dict, capability_id: str) -> dict:
    return next(c for c in settings["capabilities"] if c["id"] == capability_id)


def config(settings: dict, capability_id: str, provider_id: str) -> dict:
    return next(
        c for c in capability(settings, capability_id)["configs"] if c["provider"] == provider_id
    )


def set_env(app: FastAPI, **values: str) -> None:
    """相当于在 .env 里填好凭据后重启服务（D82）。"""
    for name, value in values.items():
        setattr(app.state.settings, name, value)


def set_capability(admin: TestClient, capability_id: str, **body):
    return admin.put(f"/api/admin/ai/capabilities/{capability_id}", json=body)


@pytest.fixture
def fake_provider(monkeypatch) -> Callable[[Callable[[httpx.Request], httpx.Response]], list]:
    """把外部请求换成假的服务商，返回收到的请求列表。"""

    def install(handler: Callable[[httpx.Request], httpx.Response]) -> list[httpx.Request]:
        requests: list[httpx.Request] = []

        def record(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return handler(request)

        monkeypatch.setattr(
            providers, "http_client", lambda: httpx.Client(transport=httpx.MockTransport(record))
        )
        return requests

    return install


def test_defaults(admin):
    settings = get_settings(admin)
    assert field(settings, "dashscope", "api_key") == {
        "key": "api_key",
        "env_var": "DASHSCOPE_API_KEY",
        "label": "API Key",
        "help": "百炼控制台 → API Key，以 sk- 开头",
        "is_set": False,
        "preview": None,
    }
    vision = capability(settings, "vision")
    assert vision["provider"] == "dashscope"
    dashscope = config(settings, "vision", "dashscope")
    assert dashscope["saved"] is False
    assert dashscope["model"] == "qwen3.8-max"
    assert dashscope["base_url"] == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert dashscope["missing_credentials"] == ["DASHSCOPE_API_KEY"]
    # 火山的模型名以控制台为准，不预填
    assert config(settings, "vision", "volcengine")["model"] == ""
    assert config(settings, "tts", "volcengine")["missing_credentials"] == [
        "VOLCENGINE_SPEECH_API_KEY"
    ]
    video = config(settings, "video", "dashscope")
    assert video["options"] == {"duration": 5, "resolution": "480P"}
    assert video["video_models"]["wanx2.1-kf2v-plus"]["resolutions"] == ["720P"]


def test_readers_cannot_access(reader):
    assert reader.get("/api/admin/ai/settings").status_code == 403
    assert reader.post("/api/admin/ai/capabilities/vision/test").status_code == 403


def test_credentials_from_env_are_never_returned(admin, app):
    set_env(app, dashscope_api_key=f"  {DASHSCOPE_KEY}  ")
    res = admin.get("/api/admin/ai/settings")
    assert DASHSCOPE_KEY not in res.text
    settings = res.json()
    assert field(settings, "dashscope", "api_key")["is_set"] is True
    assert field(settings, "dashscope", "api_key")["preview"] == "••••1234"
    assert config(settings, "vision", "dashscope")["missing_credentials"] == []


def test_credential_previews(admin, app):
    set_env(
        app,
        volcengine_ark_api_key=ARK_KEY,
        volcengine_speech_api_key="tok-abc",
    )
    settings = get_settings(admin)
    assert field(settings, "volcengine", "api_key")["preview"] == "••••5678"
    # 很短的密钥不显示末 4 位
    assert field(settings, "volcengine", "speech_api_key")["preview"] == "••••"
    # 只有空白也算没设置
    set_env(app, volcengine_ark_api_key="   ")
    assert field(get_settings(admin), "volcengine", "api_key")["is_set"] is False


def test_switch_provider_keeps_each_config(admin):
    res = set_capability(
        admin,
        "video",
        provider="dashscope",
        model="wan2.2-kf2v-flash",
        base_url="https://dashscope.aliyuncs.com/api/v1/",
        options={"resolution": "1080P"},
    )
    assert res.status_code == 200, res.text
    res = set_capability(
        admin,
        "video",
        provider="volcengine",
        model="doubao-seedance-test",
        base_url="https://ark.cn-beijing.volces.com/api/v3",
        options={"duration": 10, "resolution": "1080p"},
    )
    settings = res.json()
    assert capability(settings, "video")["provider"] == "volcengine"
    assert config(settings, "video", "volcengine")["options"] == {
        "duration": 10,
        "resolution": "1080p",
    }
    # 切到火山后，百炼的设置仍在（末尾的 / 已去掉，未给的时长用默认值）
    dashscope = config(settings, "video", "dashscope")
    assert dashscope["saved"] is True
    assert dashscope["base_url"] == "https://dashscope.aliyuncs.com/api/v1"
    assert dashscope["options"] == {"duration": 5, "resolution": "1080P"}
    # 其他能力不受影响
    assert capability(settings, "vision")["provider"] == "dashscope"


@pytest.mark.parametrize(
    ("body", "detail"),
    [
        (
            {"model": "wanx2.1-kf2v-plus", "options": {"resolution": "1080P"}},
            "该模型的清晰度只能选 720P",
        ),
        (
            {"model": "wan2.2-kf2v-flash", "options": {"duration": 10}},
            "该模型的视频时长只能选 5 秒",
        ),
        ({"model": "  "}, "请填写模型名"),
        ({"model": "m", "base_url": "ftp://x"}, "Base URL 需以 https:// 或 http:// 开头"),
    ],
)
def test_invalid_capability_settings(admin, body, detail):
    body = {"provider": "dashscope", "base_url": "https://dashscope.aliyuncs.com/api/v1"} | body
    res = set_capability(admin, "video", **body)
    assert res.status_code == 422
    assert res.json()["detail"] == detail


def test_connection_requires_credentials(admin):
    res = admin.post("/api/admin/ai/capabilities/vision/test")
    assert res.status_code == 400
    assert res.json()["detail"] == "请先在服务器的 .env 中设置 DASHSCOPE_API_KEY，然后重启服务"


def test_vision_connection_ok(admin, app, fake_provider):
    set_env(app, dashscope_api_key=DASHSCOPE_KEY)
    requests = fake_provider(
        lambda _req: httpx.Response(200, json={"choices": [{"message": {"content": "好"}}]})
    )
    res = admin.post("/api/admin/ai/capabilities/vision/test")
    assert res.json() == {"status": "ok", "message": "连接成功，模型 qwen3.8-max 可用"}
    [request] = requests
    assert str(request.url) == "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    assert request.headers["authorization"] == f"Bearer {DASHSCOPE_KEY}"


def test_connection_failure_messages(admin, app, fake_provider):
    set_env(app, dashscope_api_key=DASHSCOPE_KEY)
    fake_provider(
        lambda _req: httpx.Response(401, json={"error": {"message": "Incorrect API key provided."}})
    )
    res = admin.post("/api/admin/ai/capabilities/vision/test").json()
    assert res == {
        "status": "failed",
        "message": "服务商返回 401（API Key 无效）：Incorrect API key provided.",
    }

    def timeout(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out", request=req)

    fake_provider(timeout)
    res = admin.post("/api/admin/ai/capabilities/vision/test").json()
    assert res == {"status": "failed", "message": "连接超时，请检查 Base URL 和服务器网络"}


def test_dashscope_video_checks_key(admin, app, fake_provider):
    set_env(app, dashscope_api_key=DASHSCOPE_KEY)
    requests = fake_provider(lambda _req: httpx.Response(200, json={"data": []}))
    res = admin.post("/api/admin/ai/capabilities/video/test").json()
    assert res["status"] == "ok"
    assert str(requests[0].url) == "https://dashscope.aliyuncs.com/compatible-mode/v1/models"


def test_volcengine_connections(admin, app, fake_provider):
    set_env(
        app,
        volcengine_ark_api_key=ARK_KEY,
        volcengine_speech_api_key="speech-key",
    )
    set_capability(
        admin,
        "video",
        provider="volcengine",
        model="doubao-seedance-test",
        base_url="https://ark.cn-beijing.volces.com/api/v3",
    )
    set_capability(
        admin,
        "tts",
        provider="volcengine",
        model="seed-tts",
        base_url="https://openspeech.bytedance.com",
    )
    requests = fake_provider(lambda _req: httpx.Response(200, json={"items": []}))

    res = admin.post("/api/admin/ai/capabilities/video/test").json()
    assert res["status"] == "ok"
    assert requests[0].url.path == "/api/v3/contents/generations/tasks"
    assert requests[0].headers["authorization"] == f"Bearer {ARK_KEY}"

    res = admin.post("/api/admin/ai/capabilities/tts/test").json()
    assert res["status"] == "unsupported"
    assert len(requests) == 1


def get_models(admin: TestClient, capability_id: str, provider_id: str) -> dict:
    res = admin.get(
        f"/api/admin/ai/capabilities/{capability_id}/models", params={"provider": provider_id}
    )
    assert res.status_code == 200, res.text
    return res.json()


def test_models_need_credentials(admin):
    res = get_models(admin, "vision", "dashscope")
    assert res["message"] == "在服务器的 .env 中设置 DASHSCOPE_API_KEY 后，可以从服务商获取模型列表"
    # 仍然给出内置推荐
    assert [m["id"] for m in res["models"]] == ["qwen3.8-max", "qwen3.7-plus"]


def test_dashscope_models_filtered_and_merged(admin, app, fake_provider):
    set_env(app, dashscope_api_key=DASHSCOPE_KEY)
    requests = fake_provider(
        lambda _req: httpx.Response(
            200,
            json={
                "data": [
                    {"id": "qwen-plus", "created": 1},
                    {"id": "qwen3-max", "created": 2},
                    {"id": "qwen-vl-ocr", "created": 3},
                    {"id": "qwen3.5-ocr", "created": 4},
                    {"id": "qwen3.8-omni-flash-realtime", "created": 5},
                    {"id": "qwen3.7-text-embedding", "created": 6},
                    {"id": "qwen3.8-max", "created": 7},
                    {"id": "qwen-vl-plus", "created": 8},
                    {"id": "qwvq-typo", "created": 9},
                    {"id": "qvq-max", "created": 10},
                    {"id": "qwen3.5-flash", "created": 11},
                    {"id": "qwen3.10-plus", "created": 12},
                ]
            },
        )
    )
    res = get_models(admin, "vision", "dashscope")
    assert str(requests[0].url) == "https://dashscope.aliyuncs.com/compatible-mode/v1/models"
    assert res["message"] is None
    # 内置推荐在前（即使服务商列表里没有），其余按新旧排序。
    # Qwen3.5 起的通用模型原生多模态；纯文字的旧模型、OCR、实时语音、向量模型被筛掉
    assert [(m["id"], m["note"]) for m in res["models"]] == [
        ("qwen3.8-max", "推荐"),
        ("qwen3.7-plus", "推荐"),
        ("qwen3.10-plus", None),
        ("qwen3.5-flash", None),
        ("qvq-max", None),
        ("qwen-vl-plus", None),
    ]

    # 百炼的列表里没有首尾帧视频模型：只给内置推荐，并说明原因
    res = get_models(admin, "video", "dashscope")
    assert res["message"] == "服务商的列表里没有适合这项能力的模型，以下是推荐的模型"
    assert [m["id"] for m in res["models"]] == ["wan2.2-i2v-flash", "wan2.6-i2v-flash"]


def ark_model(model_id: str, created: int, *, domain: str, inputs, outputs, status=None) -> dict:
    model = {
        "id": model_id,
        "created": created,
        "domain": domain,
        "modalities": {"input_modalities": inputs, "output_modalities": outputs},
    }
    if status:
        model["status"] = status
    return model


def test_volcengine_models(admin, app, fake_provider):
    set_env(app, volcengine_ark_api_key=ARK_KEY)
    data = [
        ark_model(
            "doubao-seed-vision", 5, domain="VLM", inputs=["text", "image"], outputs=["text"]
        ),
        ark_model("doubao-lite", 6, domain="LLM", inputs=["text"], outputs=["text"]),
        ark_model(
            "doubao-embedding-vision", 7, domain="Embedding", inputs=["image"], outputs=["text"]
        ),
        ark_model(
            "old-vision", 1, domain="VLM", inputs=["image"], outputs=["text"], status="Shutdown"
        ),
        ark_model(
            "seedance-lite-i2v",
            3,
            domain="VideoGeneration",
            inputs=["text", "first_frame", "first_last_frame"],
            outputs=["video"],
            status="Retiring",
        ),
        ark_model("seedance-flf", 2, domain="", inputs=["image"], outputs=["video"]),
        ark_model(
            "seedance-pro-flf",
            4,
            domain="VideoGeneration",
            inputs=["text", "first_last_frame"],
            outputs=["video"],
        ),
        ark_model("seedance-t2v", 8, domain="VideoGeneration", inputs=["text"], outputs=["video"]),
    ]
    requests = fake_provider(lambda _req: httpx.Response(200, json={"data": data}))

    res = get_models(admin, "vision", "volcengine")
    assert requests[0].url.path == "/api/v3/models"
    assert [m["id"] for m in res["models"]] == ["doubao-seed-vision"]

    res = get_models(admin, "video", "volcengine")
    # 已下线、纯文生视频的不出现；即将下线的排最后；能以图片为首帧的都可以（D99）
    assert [(m["id"], m["note"], m["retiring"]) for m in res["models"]] == [
        ("seedance-pro-flf", None, False),
        ("seedance-flf", None, False),
        ("seedance-lite-i2v", "即将下线", True),
    ]


def test_volcengine_speech_has_no_model_list(admin, app, fake_provider):
    set_env(app, volcengine_speech_api_key="speech-key")
    requests = fake_provider(lambda _req: httpx.Response(500))
    res = get_models(admin, "tts", "volcengine")
    assert requests == []
    assert res["message"] == "该服务商没有提供模型列表，以下是推荐的模型"
    assert [m["id"] for m in res["models"]] == ["seed-tts-2.0", "seed-tts-1.0"]


def test_models_provider_error(admin, app, fake_provider):
    set_env(app, dashscope_api_key=DASHSCOPE_KEY)
    fake_provider(lambda _req: httpx.Response(401, json={"message": "Invalid API-key"}))
    res = get_models(admin, "vision", "dashscope")
    assert res["message"] == (
        "没能从服务商获取模型列表：服务商返回 401（API Key 无效）：Invalid API-key"
    )
    assert [m["id"] for m in res["models"]] == ["qwen3.8-max", "qwen3.7-plus"]

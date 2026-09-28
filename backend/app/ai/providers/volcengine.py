"""火山引擎：方舟（故事与台词识别、视频）+ 豆包语音（朗读）。"""

import httpx

from app.ai.providers import ModelInfo, ProviderError, TestResult
from app.ai.providers.common import chat_ping, describe_error
from app.ai.settings import CapabilityConfig


def test_connection(
    client: httpx.Client, config: CapabilityConfig, credentials: dict[str, str]
) -> TestResult:
    if config.capability == "vision":
        return chat_ping(client, config.base_url, credentials["api_key"], config.model)

    if config.capability == "video":
        # 查询视频任务列表不产生费用，用来验证方舟 Key
        res = client.get(
            f"{config.base_url.rstrip('/')}/contents/generations/tasks",
            params={"page_num": 1, "page_size": 1},
            headers={"Authorization": f"Bearer {credentials['api_key']}"},
        )
        if res.status_code != 200:
            return TestResult("failed", describe_error(res))
        return TestResult("ok", f"方舟 API Key 有效。模型 {config.model} 会在第一次生成时验证")

    # 豆包语音用自己的 API Key（请求头 X-Api-Key）；合成需要指定音色，
    # 接入朗读时（docs/06 A0、A3）再补上测试
    return TestResult("unsupported", "API Key 已设置。豆包语音暂不支持连接测试，接入朗读时补上")


def list_models(
    client: httpx.Client, config: CapabilityConfig, credentials: dict[str, str]
) -> list[ModelInfo] | None:
    # 豆包语音没有列模型的接口，只有 seed-tts-1.0 / 2.0 这几个固定的资源 ID
    if config.capability == "tts":
        return None
    res = client.get(
        f"{config.base_url.rstrip('/')}/models",
        headers={"Authorization": f"Bearer {credentials['api_key']}"},
    )
    if res.status_code != 200:
        raise ProviderError(describe_error(res))

    models = []
    for m in res.json().get("data", []):
        status = m.get("status")
        if status == "Shutdown":
            continue
        modalities = m.get("modalities") or {}
        inputs = modalities.get("input_modalities") or []
        outputs = modalities.get("output_modalities") or []
        if config.capability == "vision":
            if m.get("domain") != "VLM" or "image" not in inputs or "text" not in outputs:
                continue
            preferred, note = False, None
        else:
            if "video" not in outputs or not {"image", "first_frame", "first_last_frame"} & set(
                inputs
            ):
                continue
            preferred = "first_last_frame" in inputs
            note = "支持首尾帧" if preferred else None
        retiring = status == "Retiring"
        if retiring:
            note = "即将下线" if note is None else f"{note} · 即将下线"
        models.append(
            ModelInfo(
                id=m["id"],
                created=m.get("created") or 0,
                preferred=preferred,
                retiring=retiring,
                note=note,
            )
        )
    return models

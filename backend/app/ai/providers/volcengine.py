"""火山引擎：方舟（故事与台词识别、视频）+ 豆包语音（朗读）。"""

import httpx

from app.ai.providers import DesignedVoice, ModelInfo, ProviderError, TestResult, VideoPoll
from app.ai.providers.common import chat_ping, describe_error
from app.ai.settings import CapabilityConfig

_TTS_NOT_READY = (
    "当前朗读服务商是火山引擎，还不支持生成音色和朗读（豆包语音需先开通合成权限），"
    "请在「AI 配置」中把朗读切换到阿里云百炼"
)


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


def design_voice(
    client: httpx.Client,
    config: CapabilityConfig,
    credentials: dict[str, str],
    *,
    prompt: str,
    preview_text: str,
    name: str,
) -> DesignedVoice:
    # 火山没有按描述设计音色的接口，按 docs/06 第 6.3 节要从现成音色清单里挑；
    # 当前账号的豆包语音还没开通合成权限（D88），这部分暂未实现
    raise ProviderError(_TTS_NOT_READY)


def synthesize(
    client: httpx.Client,
    config: CapabilityConfig,
    credentials: dict[str, str],
    *,
    text: str,
    voice: str,
) -> bytes:
    raise ProviderError(_TTS_NOT_READY)


_VIDEO_NOT_READY = (
    "当前动画视频服务商是火山引擎，还不支持首尾帧动画（A0 实测账号开通的模型不支持首尾帧），"
    "请在「AI 配置」中把动画视频切换到阿里云百炼 wan2.2-kf2v-flash"
)


def submit_video(
    client: httpx.Client,
    config: CapabilityConfig,
    credentials: dict[str, str],
    *,
    frame_jpeg: bytes,
    prompt: str,
    negative_prompt: str,
    resolution: str,
) -> str:
    raise ProviderError(_VIDEO_NOT_READY)


def poll_video(
    client: httpx.Client, config: CapabilityConfig, credentials: dict[str, str], task_id: str
) -> VideoPoll:
    raise ProviderError(_VIDEO_NOT_READY)

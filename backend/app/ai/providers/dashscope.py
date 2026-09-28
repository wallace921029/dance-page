"""阿里云百炼。"""

import base64
import binascii
import re

import httpx

from app.ai.providers import DesignedVoice, ModelInfo, ProviderError, TestResult, VideoPoll
from app.ai.providers.common import chat_ping, describe_error
from app.ai.settings import CapabilityConfig

# 百炼的模型列表只有模型名，按名字筛出适合各能力的模型。
# 列表里目前没有支持音色设计的朗读模型和万相首尾帧模型，这两项主要靠内置推荐
_MODEL_PATTERNS = {
    # 旧的 -vl 系列和 QVQ；Qwen3.5 起的通用模型本身能看图，见 _is_native_multimodal
    "vision": re.compile(r"-vl-|-vl$|^qvq"),
    "tts": re.compile(r"tts-vd|cosyvoice"),
    "video": re.compile(r"kf2v"),
}
# 专做文字识别、实时语音、同传、向量的模型不适合分析整本故事
_VISION_EXCLUDE = re.compile(r"ocr|realtime|livetranslate|embedding|rerank|tts|asr")
_QWEN_VERSION = re.compile(r"^qwen(\d+)\.(\d+)-")


def _is_native_multimodal(model_id: str) -> bool:
    """Qwen3.5 及以后（3.5、3.6 … 4.x）的通用模型是原生多模态，能直接看图。"""
    m = _QWEN_VERSION.match(model_id)
    return m is not None and (int(m[1]), int(m[2])) >= (3, 5)


_SNAPSHOT = re.compile(r"\d{4}-\d{2}-\d{2}|-\d{4}$|preview")


def _version_rank(model_id: str) -> tuple:
    """版本新的在前；同一版本里常规名称在前，带日期的快照和预览版在后。
    百炼列表里的 created 与模型新旧对不上，不能用来排序。"""
    m = _QWEN_VERSION.match(model_id)
    if m:
        version = (int(m[1]), int(m[2]))
    else:
        version = (3, 0) if model_id.startswith("qwen3") else (2, 0)
    return (-version[0], -version[1], _SNAPSHOT.search(model_id) is not None, model_id)


def _suits(capability: str, model_id: str) -> bool:
    if capability == "vision":
        return (
            _MODEL_PATTERNS["vision"].search(model_id) is not None
            or _is_native_multimodal(model_id)
        ) and not _VISION_EXCLUDE.search(model_id)
    return _MODEL_PATTERNS[capability].search(model_id) is not None


def _get_models(client: httpx.Client, config: CapabilityConfig, api_key: str) -> httpx.Response:
    origin = httpx.URL(config.base_url).copy_with(path="/", query=None)
    return client.get(
        str(origin.join("/compatible-mode/v1/models")),
        headers={"Authorization": f"Bearer {api_key}"},
    )


def test_connection(
    client: httpx.Client, config: CapabilityConfig, credentials: dict[str, str]
) -> TestResult:
    api_key = credentials["api_key"]
    if config.capability == "vision":
        return chat_ping(client, config.base_url, api_key, config.model)

    # 语音、视频没有免费的测试接口，先用"列出模型"验证 Key；模型名在第一次生成时验证
    res = _get_models(client, config, api_key)
    if res.status_code != 200:
        return TestResult("failed", describe_error(res))
    return TestResult("ok", f"API Key 有效。模型 {config.model} 会在第一次生成时验证")


def list_models(
    client: httpx.Client, config: CapabilityConfig, credentials: dict[str, str]
) -> list[ModelInfo]:
    res = _get_models(client, config, credentials["api_key"])
    if res.status_code != 200:
        raise ProviderError(describe_error(res))
    ids = sorted(
        (m["id"] for m in res.json().get("data", []) if _suits(config.capability, m["id"])),
        key=_version_rank,
    )
    return [ModelInfo(id=model_id, order=i + 1) for i, model_id in enumerate(ids)]


# 按描述设计音色的模型；设计出的音色只能用于创建时指定的合成模型（qwen3-tts-vd-*）
VOICE_DESIGN_MODEL = "qwen-voice-design"
# 设计一个音色并合成试听，实测十几秒
VOICE_DESIGN_TIMEOUT = 90.0


def design_voice(
    client: httpx.Client,
    config: CapabilityConfig,
    credentials: dict[str, str],
    *,
    prompt: str,
    preview_text: str,
    name: str,
) -> DesignedVoice:
    if "tts-vd" not in config.model:
        raise ProviderError(
            f"按描述设计音色只支持 qwen3-tts-vd 系列朗读模型，当前是 {config.model}，"
            "请在「AI 配置」中更换朗读模型"
        )
    res = client.post(
        f"{config.base_url.rstrip('/')}/services/audio/tts/customization",
        headers={"Authorization": f"Bearer {credentials['api_key']}"},
        json={
            "model": VOICE_DESIGN_MODEL,
            "input": {
                "action": "create",
                "target_model": config.model,
                "voice_prompt": prompt,
                "preview_text": preview_text,
                "preferred_name": name,
            },
        },
        timeout=VOICE_DESIGN_TIMEOUT,
    )
    if res.status_code != 200:
        raise ProviderError(describe_error(res))
    try:
        output = res.json()["output"]
        return DesignedVoice(
            voice_id=output["voice"],
            preview_wav=base64.b64decode(output["preview_audio"]["data"], validate=True),
        )
    except (ValueError, KeyError, TypeError, binascii.Error) as e:
        raise ProviderError("服务商返回的音色结果无法识别") from e


# 合成一句台词（非流式，返回音频下载地址）
SYNTHESIZE_TIMEOUT = 60.0


def synthesize(
    client: httpx.Client,
    config: CapabilityConfig,
    credentials: dict[str, str],
    *,
    text: str,
    voice: str,
) -> bytes:
    res = client.post(
        f"{config.base_url.rstrip('/')}/services/aigc/multimodal-generation/generation",
        headers={"Authorization": f"Bearer {credentials['api_key']}"},
        json={"model": config.model, "input": {"text": text, "voice": voice}},
        timeout=SYNTHESIZE_TIMEOUT,
    )
    if res.status_code != 200:
        raise ProviderError(describe_error(res))
    try:
        audio = res.json()["output"]["audio"]
        if audio.get("data"):
            return base64.b64decode(audio["data"], validate=True)
        url = audio["url"]
    except (ValueError, KeyError, TypeError, binascii.Error) as e:
        raise ProviderError("服务商返回的合成结果无法识别") from e
    # 下载地址是服务商的临时存储链接（24 小时有效），不需要 Key
    download = client.get(url, timeout=SYNTHESIZE_TIMEOUT)
    if download.status_code != 200:
        raise ProviderError(f"下载合成音频失败：HTTP {download.status_code}")
    return download.content


# 首尾帧视频（万相 kf2v）：异步任务，提交后按任务 ID 查询
VIDEO_TIMEOUT = 60.0
_VIDEO_TASK_STATUS = {
    "PENDING": "running",
    "RUNNING": "running",
    "SUCCEEDED": "succeeded",
    "FAILED": "failed",
    "CANCELED": "failed",
    "UNKNOWN": "failed",
}


def _auth(credentials: dict[str, str]) -> dict[str, str]:
    return {"Authorization": f"Bearer {credentials['api_key']}"}


def _upload_image(
    client: httpx.Client, config: CapabilityConfig, credentials: dict[str, str], data: bytes
) -> str:
    """把图片上传到百炼账号下的临时存储，返回 oss:// 地址。

    绘本图片只有登录后才能访问，不能给服务商公开链接（docs/06 第 2 节）；
    做法与 dashscope SDK 传本地文件时相同：先取上传凭证，再直传 OSS。
    """
    res = client.get(
        f"{config.base_url.rstrip('/')}/uploads",
        params={"action": "getPolicy", "model": config.model},
        headers=_auth(credentials),
        timeout=VIDEO_TIMEOUT,
    )
    if res.status_code != 200:
        raise ProviderError(describe_error(res))
    try:
        policy = res.json()["data"]
        key = f"{policy['upload_dir']}/frame.jpg"
        form = {
            "OSSAccessKeyId": policy["oss_access_key_id"],
            "Signature": policy["signature"],
            "policy": policy["policy"],
            "key": key,
            "x-oss-object-acl": policy["x_oss_object_acl"],
            "x-oss-forbid-overwrite": policy["x_oss_forbid_overwrite"],
            "success_action_status": "200",
            "x-oss-content-type": "image/jpeg",
        }
        upload_host = policy["upload_host"]
    except (ValueError, KeyError, TypeError) as e:
        raise ProviderError("服务商返回的上传凭证无法识别") from e
    uploaded = client.post(
        upload_host,
        data=form,
        files={"file": ("frame.jpg", data, "image/jpeg")},
        timeout=VIDEO_TIMEOUT,
    )
    if uploaded.status_code != 200:
        raise ProviderError(f"上传画面到服务商失败：HTTP {uploaded.status_code}")
    return f"oss://{key}"


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
    if "kf2v" not in config.model:
        raise ProviderError(
            f"动画需要首尾帧视频模型（如 wan2.2-kf2v-flash），当前是 {config.model}，"
            "请在「AI 配置」中更换动画视频模型"
        )
    frame_url = _upload_image(client, config, credentials, frame_jpeg)
    res = client.post(
        f"{config.base_url.rstrip('/')}/services/aigc/image2video/video-synthesis",
        headers={
            **_auth(credentials),
            "X-DashScope-Async": "enable",
            # 让服务商读取刚上传的 oss:// 图片
            "X-DashScope-OssResourceResolve": "enable",
        },
        json={
            "model": config.model,
            "input": {
                "prompt": prompt,
                "negative_prompt": negative_prompt,
                "first_frame_url": frame_url,
                "last_frame_url": frame_url,
            },
            # 万相首尾帧模型的时长固定 5 秒，不传；提示词不让服务商改写
            "parameters": {"resolution": resolution, "prompt_extend": False},
        },
        timeout=VIDEO_TIMEOUT,
    )
    if res.status_code != 200:
        raise ProviderError(describe_error(res))
    try:
        return res.json()["output"]["task_id"]
    except (ValueError, KeyError, TypeError) as e:
        raise ProviderError("服务商返回的任务结果无法识别") from e


def poll_video(
    client: httpx.Client, config: CapabilityConfig, credentials: dict[str, str], task_id: str
) -> VideoPoll:
    res = client.get(
        f"{config.base_url.rstrip('/')}/tasks/{task_id}",
        headers=_auth(credentials),
        timeout=VIDEO_TIMEOUT,
    )
    if res.status_code != 200:
        raise ProviderError(describe_error(res))
    try:
        output = res.json()["output"]
        status = _VIDEO_TASK_STATUS.get(output["task_status"], "running")
    except (ValueError, KeyError, TypeError) as e:
        raise ProviderError("服务商返回的任务状态无法识别") from e
    if status == "succeeded":
        if not output.get("video_url"):
            return VideoPoll("failed", error="服务商没有返回视频地址")
        return VideoPoll("succeeded", video_url=output["video_url"])
    if status == "failed":
        detail = output.get("message") or output.get("code") or output.get("task_status")
        return VideoPoll("failed", error=f"服务商返回：{detail}")
    return VideoPoll("running")

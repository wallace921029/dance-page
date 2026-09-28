"""支持的 AI 服务商、能力，以及各自的默认设置（D66、D76，见 docs/06-ai-tech-design.md 第 2 节）。

模型名只是预填的默认值和建议，管理员可以填任意模型名；火山引擎的模型需要到方舟 / 豆包语音控制台
开通后才能用，名字以控制台为准，所以不预填。
"""

from dataclasses import dataclass, field
from typing import Literal

ProviderId = Literal["dashscope", "volcengine"]
CapabilityId = Literal["vision", "tts", "video"]

PROVIDER_IDS: tuple[ProviderId, ...] = ("dashscope", "volcengine")
CAPABILITY_IDS: tuple[CapabilityId, ...] = ("vision", "tts", "video")
DEFAULT_PROVIDER: ProviderId = "dashscope"


@dataclass(frozen=True)
class CredentialField:
    key: str
    # 对应 app.config.Settings 的字段，环境变量名为其大写（D82）
    setting: str
    label: str
    help: str

    @property
    def env_var(self) -> str:
        return self.setting.upper()


@dataclass(frozen=True)
class Provider:
    id: ProviderId
    name: str
    fields: tuple[CredentialField, ...]


@dataclass(frozen=True)
class VideoOptions:
    """视频模型可选的时长（秒）和清晰度（D77）。"""

    durations: tuple[int, ...]
    resolutions: tuple[str, ...]
    default_duration: int
    default_resolution: str


@dataclass(frozen=True)
class ProviderDefaults:
    base_url: str
    model: str
    model_suggestions: tuple[str, ...] = ()
    # 该能力需要该服务商的哪些凭据
    required_fields: tuple[str, ...] = ("api_key",)
    # 仅视频：已知模型的可选项；未知模型用 video_fallback
    video_models: dict[str, VideoOptions] = field(default_factory=dict)
    video_fallback: VideoOptions | None = None

    def video_options(self, model: str) -> VideoOptions | None:
        return self.video_models.get(model, self.video_fallback)


@dataclass(frozen=True)
class Capability:
    id: CapabilityId
    name: str
    description: str
    providers: dict[ProviderId, ProviderDefaults]


PROVIDERS: dict[ProviderId, Provider] = {
    "dashscope": Provider(
        id="dashscope",
        name="阿里云百炼",
        fields=(
            CredentialField(
                "api_key",
                "dashscope_api_key",
                "API Key",
                help="百炼控制台 → API Key，以 sk- 开头",
            ),
        ),
    ),
    "volcengine": Provider(
        id="volcengine",
        name="火山引擎",
        fields=(
            CredentialField(
                "api_key",
                "volcengine_ark_api_key",
                "方舟 API Key",
                help="火山方舟控制台 → API Key，用于故事与台词识别、动画视频",
            ),
            CredentialField(
                "speech_api_key",
                "volcengine_speech_api_key",
                "豆包语音 API Key",
                help="豆包语音控制台（新版）→ API Key，用于朗读；与方舟的 Key 不是同一个",
            ),
        ),
    ),
}

_ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
_DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/api/v1"

CAPABILITIES: dict[CapabilityId, Capability] = {
    "vision": Capability(
        id="vision",
        name="故事与台词识别",
        description="多模态大模型：通读整本书，写出故事、角色、音色提示词、台词和动作描述",
        providers={
            "dashscope": ProviderDefaults(
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                # Qwen3.5 起的通用模型原生多模态；百炼文档建议看图任务从 qwen3.8-max 开始
                model="qwen3.8-max",
                model_suggestions=("qwen3.8-max", "qwen3.7-plus"),
            ),
            "volcengine": ProviderDefaults(base_url=_ARK_BASE_URL, model=""),
        },
    ),
    "tts": Capability(
        id="tts",
        name="朗读",
        description="按角色的音色合成朗读；百炼可按音色提示词设计专属音色",
        providers={
            "dashscope": ProviderDefaults(
                base_url=_DASHSCOPE_BASE_URL,
                model="qwen3-tts-vd-2026-01-26",
                model_suggestions=("qwen3-tts-vd-2026-01-26", "cosyvoice-v3-plus"),
            ),
            "volcengine": ProviderDefaults(
                base_url="https://openspeech.bytedance.com",
                # 豆包语音的"模型"即请求头 X-Api-Resource-Id
                model="seed-tts-2.0",
                model_suggestions=("seed-tts-2.0", "seed-tts-1.0"),
                required_fields=("speech_api_key",),
            ),
        },
    ),
    "video": Capability(
        id="video",
        name="动画视频",
        description="首尾帧都用原页面图片，让画面里的主角做一个简单的循环动作",
        providers={
            "dashscope": ProviderDefaults(
                base_url=_DASHSCOPE_BASE_URL,
                model="wan2.2-kf2v-flash",
                model_suggestions=("wan2.2-kf2v-flash", "wanx2.1-kf2v-plus"),
                video_models={
                    # 万相首尾帧模型的时长固定 5 秒
                    "wan2.2-kf2v-flash": VideoOptions((5,), ("480P", "720P", "1080P"), 5, "720P"),
                    "wanx2.1-kf2v-plus": VideoOptions((5,), ("720P",), 5, "720P"),
                },
                video_fallback=VideoOptions((5,), ("480P", "720P", "1080P"), 5, "720P"),
            ),
            "volcengine": ProviderDefaults(
                base_url=_ARK_BASE_URL,
                model="",
                # Seedance 的实际可选范围在试验（A0）时按所开通的模型确认
                video_fallback=VideoOptions(
                    (3, 4, 5, 6, 8, 10), ("480p", "720p", "1080p"), 5, "720p"
                ),
            ),
        },
    ),
}

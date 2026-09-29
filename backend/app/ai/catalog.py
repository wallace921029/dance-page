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
    # 仅视频：已知模型的可选项，键是模型名或模型名前缀（火山的模型名带日期后缀，
    # 如 doubao-seedance-2-0-260128）；都对不上时用 video_fallback
    video_models: dict[str, VideoOptions] = field(default_factory=dict)
    video_fallback: VideoOptions | None = None

    def video_options(self, model: str) -> VideoOptions | None:
        if model in self.video_models:
            return self.video_models[model]
        # 最长的前缀优先：doubao-seedance-2-0-fast 不会被当成 doubao-seedance-2-0
        prefixes = [key for key in self.video_models if model.startswith(key)]
        if prefixes:
            return self.video_models[max(prefixes, key=len)]
        return self.video_fallback


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
        description="以原页面图片为首帧，让画面里的主角动起来；生成后正放再倒放，做成无缝循环",
        providers={
            "dashscope": ProviderDefaults(
                base_url=_DASHSCOPE_BASE_URL,
                model="wan2.2-i2v-flash",
                model_suggestions=("wan2.2-i2v-flash", "wan2.6-i2v-flash"),
                video_models={
                    # 万相图生视频（只给首帧，D99）；清晰度默认取模型支持的最低一档（D102）
                    "wan2.2-i2v-flash": VideoOptions((5,), ("480P", "720P", "1080P"), 5, "480P"),
                    "wan2.6-i2v-flash": VideoOptions((3, 5, 10), ("720P", "1080P"), 5, "720P"),
                    # 首尾帧模型（D96 起用过；首尾帧相同时几乎不动，不再推荐）
                    "wan2.2-kf2v-flash": VideoOptions((5,), ("480P", "720P", "1080P"), 5, "480P"),
                    "wanx2.1-kf2v-plus": VideoOptions((5,), ("720P",), 5, "720P"),
                },
                video_fallback=VideoOptions((5,), ("480P", "720P", "1080P"), 5, "480P"),
            ),
            "volcengine": ProviderDefaults(
                base_url=_ARK_BASE_URL,
                model="",
                video_models={
                    # Seedance 2.0：时长 4–15 秒；Fast 最高 720p
                    "doubao-seedance-2-0-fast": VideoOptions(
                        (4, 5, 6, 8, 10, 12, 15), ("480p", "720p"), 5, "480p"
                    ),
                    "doubao-seedance-2-0": VideoOptions(
                        (4, 5, 6, 8, 10, 12, 15), ("480p", "720p", "1080p"), 5, "480p"
                    ),
                },
                # 其他 Seedance 型号的范围各不相同，5 秒、10 秒各代都支持
                video_fallback=VideoOptions((5, 10), ("480p", "720p", "1080p"), 5, "480p"),
            ),
        },
    ),
}

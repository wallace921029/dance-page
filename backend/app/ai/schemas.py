from typing import Literal

from pydantic import BaseModel, field_validator

from app.ai.catalog import CapabilityId, ProviderId


class CredentialFieldOut(BaseModel):
    key: str
    # 在 .env 里设置的环境变量名（D82）
    env_var: str
    label: str
    help: str
    is_set: bool
    # 只给末 4 位（"••••abcd"），永远不返回完整的 Key
    preview: str | None


class ProviderOut(BaseModel):
    id: ProviderId
    name: str
    fields: list[CredentialFieldOut]


class VideoOptionsOut(BaseModel):
    durations: list[int]
    resolutions: list[str]
    default_duration: int
    default_resolution: str


class ProviderConfigOut(BaseModel):
    provider: ProviderId
    model: str
    base_url: str
    options: dict
    # False 表示还没保存过，以上是默认值
    saved: bool
    default_model: str
    default_base_url: str
    model_suggestions: list[str]
    # 仅视频：已知模型的可选项，未知模型用 video_fallback
    video_models: dict[str, VideoOptionsOut]
    video_fallback: VideoOptionsOut | None
    # 这项能力在这家服务商上还缺哪些凭据（要在 .env 里设置的环境变量名）
    missing_credentials: list[str]


class CapabilityOut(BaseModel):
    id: CapabilityId
    name: str
    description: str
    # 当前使用的服务商
    provider: ProviderId
    configs: list[ProviderConfigOut]


class AiSettingsOut(BaseModel):
    providers: list[ProviderOut]
    capabilities: list[CapabilityOut]


class CapabilityUpdate(BaseModel):
    provider: ProviderId
    model: str
    base_url: str
    options: dict = {}

    @field_validator("model")
    @classmethod
    def _model(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("请填写模型名")
        if len(value) > 200:
            raise ValueError("模型名太长")
        return value

    @field_validator("base_url")
    @classmethod
    def _base_url(cls, value: str) -> str:
        value = value.strip().rstrip("/")
        if not value.startswith(("https://", "http://")) or len(value) > 500:
            raise ValueError("Base URL 需以 https:// 或 http:// 开头")
        return value


class TestResultOut(BaseModel):
    status: Literal["ok", "failed", "unsupported"]
    message: str


class ModelOptionOut(BaseModel):
    id: str
    # 如"推荐""即将下线"
    note: str | None
    retiring: bool


class ModelListOut(BaseModel):
    models: list[ModelOptionOut]
    # 没能从服务商取到列表时的说明（未设置 Key、没有列模型的接口、请求失败等）
    message: str | None

"""AI 配置：服务商凭据（来自 .env）、每种能力当前用哪家、各家的模型设置。"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.ai.catalog import (
    CAPABILITIES,
    DEFAULT_PROVIDER,
    PROVIDERS,
    CapabilityId,
    ProviderId,
)
from app.config import Settings
from app.models import AiCapability, AiCapabilityConfig


def load_credentials(settings: Settings, provider: ProviderId) -> dict[str, str]:
    """该服务商在 .env 里已设置的凭据（字段 key → 值），未设置的不出现（D82）。"""
    values = {f.key: getattr(settings, f.setting).strip() for f in PROVIDERS[provider].fields}
    return {key: value for key, value in values.items() if value}


@dataclass
class CapabilityConfig:
    capability: CapabilityId
    provider: ProviderId
    model: str
    base_url: str
    options: dict
    # False 表示还没保存过，以上是默认值
    saved: bool


def active_provider(db: Session, capability: CapabilityId) -> ProviderId:
    row = db.get(AiCapability, capability)
    return row.provider if row else DEFAULT_PROVIDER


def load_config(db: Session, capability: CapabilityId, provider: ProviderId) -> CapabilityConfig:
    row = db.get(AiCapabilityConfig, (capability, provider))
    if row is not None:
        return CapabilityConfig(
            capability, provider, row.model, row.base_url, dict(row.options), saved=True
        )
    defaults = CAPABILITIES[capability].providers[provider]
    return CapabilityConfig(
        capability,
        provider,
        defaults.model,
        defaults.base_url,
        default_options(capability, provider, defaults.model),
        saved=False,
    )


def load_active_config(db: Session, capability: CapabilityId) -> CapabilityConfig:
    return load_config(db, capability, active_provider(db, capability))


def default_options(capability: CapabilityId, provider: ProviderId, model: str) -> dict:
    video = CAPABILITIES[capability].providers[provider].video_options(model)
    if capability != "video" or video is None:
        return {}
    return {"duration": video.default_duration, "resolution": video.default_resolution}


def normalize_options(
    capability: CapabilityId, provider: ProviderId, model: str, options: dict
) -> dict:
    """校验并补全能力相关的设置；不合法时抛出带中文提示的 ValueError。"""
    if capability != "video":
        return {}
    video = CAPABILITIES[capability].providers[provider].video_options(model)
    assert video is not None
    duration = options.get("duration", video.default_duration)
    resolution = options.get("resolution", video.default_resolution)
    if duration not in video.durations:
        allowed = "、".join(f"{d} 秒" for d in video.durations)
        raise ValueError(f"该模型的视频时长只能选 {allowed}")
    if resolution not in video.resolutions:
        raise ValueError(f"该模型的清晰度只能选 {'、'.join(video.resolutions)}")
    return {"duration": duration, "resolution": resolution}


def save_config(
    db: Session,
    capability: CapabilityId,
    provider: ProviderId,
    *,
    model: str,
    base_url: str,
    options: dict,
) -> None:
    """保存该服务商的设置，并把该能力切换到这家服务商。"""
    row = db.get(AiCapabilityConfig, (capability, provider))
    if row is None:
        row = AiCapabilityConfig(capability=capability, provider=provider)
        db.add(row)
    row.model = model
    row.base_url = base_url
    row.options = normalize_options(capability, provider, model, options)

    active = db.get(AiCapability, capability)
    if active is None:
        db.add(AiCapability(capability=capability, provider=provider))
    else:
        active.provider = provider


def missing_credentials(
    capability: CapabilityId, provider: ProviderId, credentials: dict[str, str]
) -> list[str]:
    """该能力在该服务商上还缺哪些凭据（返回要在 .env 里设置的环境变量名）。"""
    required = CAPABILITIES[capability].providers[provider].required_fields
    env_vars = {f.key: f.env_var for f in PROVIDERS[provider].fields}
    return [env_vars[key] for key in required if not credentials.get(key)]

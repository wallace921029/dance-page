from fastapi import APIRouter, HTTPException, status
from sqlalchemy.orm import Session

from app.ai.catalog import (
    CAPABILITIES,
    PROVIDER_IDS,
    PROVIDERS,
    CapabilityId,
    ProviderId,
    VideoOptions,
)
from app.ai.providers import ModelInfo, ProviderError, list_models, test_connection
from app.ai.schemas import (
    AiSettingsOut,
    CapabilityOut,
    CapabilityUpdate,
    CredentialFieldOut,
    ModelListOut,
    ModelOptionOut,
    ProviderConfigOut,
    ProviderOut,
    TestResultOut,
    VideoOptionsOut,
)
from app.ai.settings import (
    active_provider,
    load_active_config,
    load_config,
    load_credentials,
    missing_credentials,
    save_config,
)
from app.config import Settings
from app.deps import AppSettings, CurrentAdmin, DbSession

router = APIRouter(prefix="/admin/ai", tags=["AI 配置"])


def _preview(value: str) -> str:
    return "••••" + value[-4:] if len(value) > 8 else "••••"


def _video_out(options: VideoOptions) -> VideoOptionsOut:
    return VideoOptionsOut(
        durations=list(options.durations),
        resolutions=list(options.resolutions),
        default_duration=options.default_duration,
        default_resolution=options.default_resolution,
    )


def _settings_out(db: Session, settings: Settings) -> AiSettingsOut:
    credentials: dict[ProviderId, dict[str, str]] = {
        p: load_credentials(settings, p) for p in PROVIDER_IDS
    }
    providers = [
        ProviderOut(
            id=provider.id,
            name=provider.name,
            fields=[
                CredentialFieldOut(
                    key=f.key,
                    env_var=f.env_var,
                    label=f.label,
                    help=f.help,
                    is_set=f.key in credentials[provider.id],
                    preview=_preview(credentials[provider.id][f.key])
                    if f.key in credentials[provider.id]
                    else None,
                )
                for f in provider.fields
            ],
        )
        for provider in PROVIDERS.values()
    ]

    capabilities = []
    for capability in CAPABILITIES.values():
        configs = []
        for provider_id in PROVIDER_IDS:
            config = load_config(db, capability.id, provider_id)
            defaults = capability.providers[provider_id]
            configs.append(
                ProviderConfigOut(
                    provider=provider_id,
                    model=config.model,
                    base_url=config.base_url,
                    options=config.options,
                    saved=config.saved,
                    default_model=defaults.model,
                    default_base_url=defaults.base_url,
                    model_suggestions=list(defaults.model_suggestions),
                    video_models={k: _video_out(v) for k, v in defaults.video_models.items()},
                    video_fallback=_video_out(defaults.video_fallback)
                    if defaults.video_fallback
                    else None,
                    missing_credentials=missing_credentials(
                        capability.id, provider_id, credentials[provider_id]
                    ),
                )
            )
        capabilities.append(
            CapabilityOut(
                id=capability.id,
                name=capability.name,
                description=capability.description,
                provider=active_provider(db, capability.id),
                configs=configs,
            )
        )
    return AiSettingsOut(providers=providers, capabilities=capabilities)


@router.get("/settings")
def get_ai_settings(_admin: CurrentAdmin, db: DbSession, settings: AppSettings) -> AiSettingsOut:
    return _settings_out(db, settings)


@router.put("/capabilities/{capability}")
def update_capability(
    capability: CapabilityId,
    body: CapabilityUpdate,
    _admin: CurrentAdmin,
    db: DbSession,
    settings: AppSettings,
) -> AiSettingsOut:
    try:
        save_config(
            db,
            capability,
            body.provider,
            model=body.model,
            base_url=body.base_url,
            options=body.options,
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from e
    db.commit()
    return _settings_out(db, settings)


@router.post("/capabilities/{capability}/test")
def test_capability(
    capability: CapabilityId, _admin: CurrentAdmin, db: DbSession, settings: AppSettings
) -> TestResultOut:
    """用已保存的设置测试当前服务商能否连通。"""
    config = load_active_config(db, capability)
    credentials = load_credentials(settings, config.provider)
    if missing := missing_credentials(capability, config.provider, credentials):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"请先在服务器的 .env 中设置 {'、'.join(missing)}，然后重启服务",
        )
    result = test_connection(config, credentials)
    return TestResultOut(status=result.status, message=result.message)


@router.get("/capabilities/{capability}/models")
def get_models(
    capability: CapabilityId,
    provider: ProviderId,
    _admin: CurrentAdmin,
    db: DbSession,
    settings: AppSettings,
) -> ModelListOut:
    """这项能力在某家服务商上可选的模型：服务商的模型列表 + 内置推荐（免费的查询）。"""
    config = load_config(db, capability, provider)
    credentials = load_credentials(settings, provider)
    remote: list[ModelInfo] = []
    message = None
    if missing := missing_credentials(capability, provider, credentials):
        message = f"在服务器的 .env 中设置 {'、'.join(missing)} 后，可以从服务商获取模型列表"
    else:
        try:
            result = list_models(config, credentials)
        except ProviderError as e:
            message = f"没能从服务商获取模型列表：{e}"
        else:
            if result is None:
                message = "该服务商没有提供模型列表，以下是推荐的模型"
            elif not result:
                message = "服务商的列表里没有适合这项能力的模型，以下是推荐的模型"
            else:
                remote = result

    by_id = {m.id: m for m in remote}
    suggestions = CAPABILITIES[capability].providers[provider].model_suggestions
    # 内置推荐排最前；服务商的其他模型按"未下线 → 更适合 → 较新"排序
    models = [
        ModelOptionOut(
            id=model_id,
            note="推荐"
            if model_id not in by_id or not by_id[model_id].note
            else f"推荐 · {by_id[model_id].note}",
            retiring=model_id in by_id and by_id[model_id].retiring,
        )
        for model_id in suggestions
    ]
    others = sorted(
        (m for m in remote if m.id not in suggestions),
        key=lambda m: (m.retiring, not m.preferred, m.order, -m.created, m.id),
    )
    models += [ModelOptionOut(id=m.id, note=m.note, retiring=m.retiring) for m in others]
    return ModelListOut(models=models, message=message)

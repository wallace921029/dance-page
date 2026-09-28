"""各服务商的适配器（docs/06-ai-tech-design.md 第 1、2 节）。

连接测试、列模型、设计音色、朗读合成经由这里分派到各家适配器；视频在 A4 按同样的方式加进来。
"""

from dataclasses import dataclass
from typing import Literal

import httpx

from app.ai.settings import CapabilityConfig

# 外部请求的超时（秒）。连接测试是管理员点按钮时同步执行的，不能等太久
TEST_TIMEOUT = 20


@dataclass
class TestResult:
    # unsupported：该服务商的这项能力暂时没有可用的测试方式
    status: Literal["ok", "failed", "unsupported"]
    message: str


def http_client() -> httpx.Client:
    """测试里会替换成假的服务商。

    不读取 HTTP(S)_PROXY / ALL_PROXY 等环境变量：两家都是国内服务，服务器直连即可；
    开发机上的系统代理（如 socks://）反而会让请求失败。
    """
    return httpx.Client(timeout=TEST_TIMEOUT, trust_env=False)


class ProviderError(Exception):
    """服务商返回错误或连不上；消息是给管理员看的中文说明。"""


@dataclass
class ModelInfo:
    id: str
    created: int = 0
    # 更适合这项能力（如标明支持首尾帧的视频模型），排在前面
    preferred: bool = False
    # 服务商标记为即将下线
    retiring: bool = False
    note: str | None = None
    # 适配器给出的排序（小的在前）；为 0 时按 created 从新到旧
    order: int = 0


def _adapter(provider: str):
    from app.ai.providers import dashscope, volcengine

    return {"dashscope": dashscope, "volcengine": volcengine}[provider]


def _network_error(e: httpx.HTTPError) -> str:
    if isinstance(e, httpx.TimeoutException):
        return "连接超时，请检查 Base URL 和服务器网络"
    return f"无法连接服务商：{type(e).__name__}"


def test_connection(config: CapabilityConfig, credentials: dict[str, str]) -> TestResult:
    try:
        with http_client() as client:
            return _adapter(config.provider).test_connection(client, config, credentials)
    except httpx.HTTPError as e:
        return TestResult("failed", _network_error(e))


def list_models(config: CapabilityConfig, credentials: dict[str, str]) -> list[ModelInfo] | None:
    """服务商上适合这项能力的模型（免费的查询）；None 表示该服务商没有列模型的接口。"""
    try:
        with http_client() as client:
            return _adapter(config.provider).list_models(client, config, credentials)
    except httpx.HTTPError as e:
        raise ProviderError(_network_error(e)) from e


@dataclass
class DesignedVoice:
    # 服务商返回的音色 ID，合成时用它指定音色
    voice_id: str
    # 试听音频（WAV）
    preview_wav: bytes


def design_voice(
    config: CapabilityConfig,
    credentials: dict[str, str],
    *,
    prompt: str,
    preview_text: str,
    name: str,
) -> DesignedVoice:
    """按音色提示词为当前朗读模型设计一个音色（docs/06 第 6.3 节）。"""
    try:
        with http_client() as client:
            return _adapter(config.provider).design_voice(
                client, config, credentials, prompt=prompt, preview_text=preview_text, name=name
            )
    except httpx.HTTPError as e:
        raise ProviderError(_network_error(e)) from e


def synthesize(
    config: CapabilityConfig, credentials: dict[str, str], *, text: str, voice: str
) -> bytes:
    """用指定音色合成一句台词，返回音频文件内容（格式由服务商决定，之后统一解码）。"""
    try:
        with http_client() as client:
            return _adapter(config.provider).synthesize(
                client, config, credentials, text=text, voice=voice
            )
    except httpx.HTTPError as e:
        raise ProviderError(_network_error(e)) from e

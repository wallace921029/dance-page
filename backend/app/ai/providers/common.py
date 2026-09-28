"""各适配器共用的请求工具。"""

import httpx

from app.ai.providers import TestResult

_MAX_ERROR_LENGTH = 200


def describe_error(res: httpx.Response) -> str:
    """把服务商的错误响应转成给管理员看的一句话（不包含请求里的 Key）。"""
    detail = ""
    try:
        body = res.json()
    except ValueError:
        body = None
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict):
            detail = error.get("message") or error.get("code") or ""
        elif isinstance(error, str):
            detail = error
        else:
            detail = body.get("message") or body.get("code") or ""
    if not detail:
        detail = res.text or res.reason_phrase
    hint = {401: "API Key 无效", 403: "没有权限或未开通该服务", 404: "地址或模型不存在"}.get(
        res.status_code
    )
    message = f"服务商返回 {res.status_code}"
    if hint:
        message += f"（{hint}）"
    return f"{message}：{str(detail)[:_MAX_ERROR_LENGTH]}"


def chat_ping(client: httpx.Client, base_url: str, api_key: str, model: str) -> TestResult:
    """用 OpenAI 兼容接口发一条极短的对话，验证 Base URL、Key 和模型名都可用。"""
    res = client.post(
        f"{base_url.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": model,
            "messages": [{"role": "user", "content": "请只回复：好"}],
            "max_tokens": 8,
        },
    )
    if res.status_code != 200:
        return TestResult("failed", describe_error(res))
    try:
        res.json()["choices"][0]
    except (ValueError, KeyError, IndexError, TypeError):
        return TestResult("failed", "服务商返回的内容无法识别，请检查 Base URL")
    return TestResult("ok", f"连接成功，模型 {model} 可用")
